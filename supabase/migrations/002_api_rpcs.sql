-- Transactional operations invoked by Flask through Supabase's HTTPS RPC API.
-- Run after 001_initial_schema.sql. The Flask app does not connect to Postgres.

create or replace function public.api_release_borrowing_request(
  p_borrowing_id bigint,
  p_processed_by bigint
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_borrowing public.borrowings%rowtype;
  v_item record;
  v_equipment public.equipment%rowtype;
begin
  select * into v_borrowing from public.borrowings
  where borrowing_id = p_borrowing_id for update;
  if not found then raise exception 'Borrowing request was not found.'; end if;
  if v_borrowing.status <> 'Approved' then raise exception 'Only Approved requests can be released.'; end if;

  for v_item in
    select * from public.borrowing_items
    where borrowing_id = p_borrowing_id order by equipment_id for update
  loop
    select * into v_equipment from public.equipment
    where equipment_id = v_item.equipment_id for update;
    if not found then raise exception 'A requested equipment record no longer exists.'; end if;
    if v_item.quantity_borrowed > v_equipment.available_stock then
      raise exception 'Insufficient stock for %.', v_equipment.equipment_name;
    end if;
    update public.equipment set available_stock = available_stock - v_item.quantity_borrowed
    where equipment_id = v_item.equipment_id;
    update public.borrowing_items
    set remaining_quantity = quantity_borrowed - quantity_returned
    where borrowing_item_id = v_item.borrowing_item_id;
  end loop;

  update public.borrowings
  set status = 'Active', processed_by = p_processed_by, borrowed_at = now()
  where borrowing_id = p_borrowing_id;
  insert into public.audit_logs (user_id, action, table_name, record_id, description)
  values (p_processed_by, 'UPDATE', 'borrowings', p_borrowing_id,
    format('Released equipment for borrowing request #%s', p_borrowing_id));
  return jsonb_build_object('borrowing_id', p_borrowing_id, 'status', 'Active');
end;
$$;

create or replace function public.api_approve_pending_request(
  p_borrower_id bigint,
  p_processed_by bigint
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare v_borrowing_id bigint;
begin
  select borrowing_id into v_borrowing_id from public.borrowings
  where borrower_id = p_borrower_id and status = 'Pending'
  order by created_at, borrowing_id limit 1 for update;
  if not found then raise exception 'This borrower has no pending borrowing request to approve.'; end if;
  update public.borrowings set status = 'Approved', processed_by = p_processed_by
  where borrowing_id = v_borrowing_id;
  return public.api_release_borrowing_request(v_borrowing_id, p_processed_by);
end;
$$;

create or replace function public.api_create_direct_borrowing(
  p_borrower_id bigint,
  p_processed_by bigint,
  p_due_date date,
  p_purpose text,
  p_items jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_borrowing_id bigint;
  v_item record;
  v_equipment public.equipment%rowtype;
begin
  perform 1 from public.borrowers where borrower_id = p_borrower_id for update;
  if not found then raise exception 'The selected borrower no longer exists.'; end if;
  if jsonb_array_length(p_items) = 0 then raise exception 'At least one equipment item is required.'; end if;

  for v_item in select * from jsonb_to_recordset(p_items) as x(equipment_id bigint, quantity integer) order by equipment_id loop
    select * into v_equipment from public.equipment where equipment_id = v_item.equipment_id for update;
    if not found then raise exception 'One selected equipment record no longer exists.'; end if;
    if v_item.quantity <= 0 or v_item.quantity > v_equipment.available_stock then
      raise exception 'Insufficient stock for %.', v_equipment.equipment_name;
    end if;
  end loop;

  insert into public.borrowings (borrower_id, processed_by, expected_return_date, purpose_notes, status)
  values (p_borrower_id, p_processed_by, p_due_date, p_purpose, 'Active')
  returning borrowing_id into v_borrowing_id;
  for v_item in select * from jsonb_to_recordset(p_items) as x(equipment_id bigint, quantity integer) loop
    insert into public.borrowing_items (borrowing_id, equipment_id, quantity_borrowed, quantity_returned, remaining_quantity)
    values (v_borrowing_id, v_item.equipment_id, v_item.quantity, 0, v_item.quantity);
    update public.equipment set available_stock = available_stock - v_item.quantity
    where equipment_id = v_item.equipment_id;
  end loop;
  insert into public.audit_logs (user_id, action, table_name, record_id, description)
  values (p_processed_by, 'CREATE', 'borrowings', v_borrowing_id,
    format('Created borrowing transaction #%s', v_borrowing_id));
  return jsonb_build_object('borrowing_id', v_borrowing_id, 'status', 'Active');
end;
$$;

create or replace function public.api_submit_staff_request(
  p_user_id bigint,
  p_equipment_id bigint,
  p_quantity integer,
  p_date_needed date,
  p_expected_return date,
  p_purpose text,
  p_notes text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_borrower_id bigint;
  v_borrowing_id bigint;
  v_user public.users%rowtype;
  v_equipment public.equipment%rowtype;
  v_reserved integer;
begin
  select * into v_user from public.users where user_id = p_user_id for update;
  if not found then raise exception 'User account not found.'; end if;
  select borrower_id into v_borrower_id from public.borrowers where user_id = p_user_id for update;
  if not found then
    select borrower_id into v_borrower_id from public.borrowers
    where user_id is null and (email = v_user.email or full_name = v_user.full_name)
    order by borrower_id limit 1 for update;
    if found then
      update public.borrowers set user_id = p_user_id where borrower_id = v_borrower_id;
    else
      insert into public.borrowers (user_id, full_name, contact_number, address, email)
      values (p_user_id, v_user.full_name, v_user.contact_number, v_user.address, v_user.email)
      returning borrower_id into v_borrower_id;
    end if;
  end if;
  select * into v_equipment from public.equipment where equipment_id = p_equipment_id for update;
  if not found then raise exception 'The selected equipment no longer exists.'; end if;
  select coalesce(sum(bi.quantity_borrowed), 0) into v_reserved
  from public.borrowing_items bi join public.borrowings b on b.borrowing_id = bi.borrowing_id
  where bi.equipment_id = p_equipment_id and b.status in ('Pending', 'Approved');
  if p_quantity <= 0 or p_quantity > v_equipment.available_stock - v_reserved then
    raise exception 'The requested quantity is not available.';
  end if;
  insert into public.borrowings (borrower_id, date_needed, expected_return_date, purpose_notes, additional_notes, status)
  values (v_borrower_id, p_date_needed, p_expected_return, p_purpose, p_notes, 'Pending')
  returning borrowing_id into v_borrowing_id;
  insert into public.borrowing_items (borrowing_id, equipment_id, quantity_borrowed, quantity_returned, remaining_quantity)
  values (v_borrowing_id, p_equipment_id, p_quantity, 0, p_quantity);
  insert into public.audit_logs (user_id, action, table_name, record_id, description)
  values (p_user_id, 'CREATE', 'borrowings', v_borrowing_id,
    format('Submitted borrowing request #%s', v_borrowing_id));
  return jsonb_build_object('borrowing_id', v_borrowing_id, 'status', 'Pending');
end;
$$;

create or replace function public.api_save_return(
  p_borrowing_id bigint,
  p_return_date date,
  p_items jsonb,
  p_received_by bigint,
  p_notes text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_item record;
  v_current public.borrowing_items%rowtype;
  v_equipment public.equipment%rowtype;
  v_remaining integer;
  v_status text;
begin
  perform 1 from public.borrowings where borrowing_id = p_borrowing_id
    and status in ('Active', 'Partially Returned') for update;
  if not found then raise exception 'This borrowing transaction is not active or was not found.'; end if;
  for v_item in select * from jsonb_to_recordset(p_items) as x(borrowing_item_id bigint, quantity integer) order by borrowing_item_id loop
    select * into v_current from public.borrowing_items
    where borrowing_item_id = v_item.borrowing_item_id and borrowing_id = p_borrowing_id for update;
    if not found then raise exception 'One return item does not belong to this transaction.'; end if;
    select * into v_equipment from public.equipment where equipment_id = v_current.equipment_id for update;
    if v_item.quantity <= 0 or v_item.quantity > v_current.quantity_borrowed - v_current.quantity_returned then
      raise exception 'Returned quantity exceeds the remaining quantity.';
    end if;
    if v_equipment.available_stock + v_item.quantity > v_equipment.total_stock then
      raise exception 'Stock integrity check failed for %.', v_equipment.equipment_name;
    end if;
    update public.borrowing_items set quantity_returned = quantity_returned + v_item.quantity,
      remaining_quantity = quantity_borrowed - quantity_returned
      where borrowing_item_id = v_current.borrowing_item_id;
    update public.equipment set available_stock = available_stock + v_item.quantity
      where equipment_id = v_current.equipment_id;
    insert into public.return_records (borrowing_item_id, received_by, quantity_returned, return_date, notes)
    values (v_current.borrowing_item_id, p_received_by, v_item.quantity, p_return_date, p_notes);
  end loop;
  select coalesce(sum(quantity_borrowed - quantity_returned), 0) into v_remaining
    from public.borrowing_items where borrowing_id = p_borrowing_id;
  v_status := case when v_remaining = 0 then 'Returned' else 'Partially Returned' end;
  update public.borrowings set status = v_status where borrowing_id = p_borrowing_id;
  insert into public.audit_logs (user_id, action, table_name, record_id, description)
  values (p_received_by, 'RETURN', 'borrowings', p_borrowing_id,
    format('Recorded return for transaction #%s; status: %s', p_borrowing_id, v_status));
  return jsonb_build_object('borrowing_id', p_borrowing_id, 'status', v_status);
end;
$$;

revoke all on function public.api_release_borrowing_request(bigint, bigint) from public;
revoke all on function public.api_approve_pending_request(bigint, bigint) from public;
revoke all on function public.api_create_direct_borrowing(bigint, bigint, date, text, jsonb) from public;
revoke all on function public.api_submit_staff_request(bigint, bigint, integer, date, date, text, text) from public;
revoke all on function public.api_save_return(bigint, date, jsonb, bigint, text) from public;
grant execute on function public.api_release_borrowing_request(bigint, bigint) to service_role;
grant execute on function public.api_approve_pending_request(bigint, bigint) to service_role;
grant execute on function public.api_create_direct_borrowing(bigint, bigint, date, text, jsonb) to service_role;
grant execute on function public.api_submit_staff_request(bigint, bigint, integer, date, date, text, text) to service_role;
grant execute on function public.api_save_return(bigint, date, jsonb, bigint, text) to service_role;
