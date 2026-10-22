"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

const proxy = (path) => `/api/proxy${path}`;
const adminLinks = [["/dashboard", "Dashboard", "grid"], ["/equipment", "Equipment", "box"], ["/borrowers", "Borrowers", "people"], ["/borrowings", "New Transaction", "plus"], ["/admin/borrowing-requests", "Requests", "inbox"], ["/returns", "Returns", "return"], ["/reports", "Reports", "chart"], ["/audit-logs", "Audit Trail", "clock"], ["/about", "About", "info"]];
const staffLinks = [["/staff-dashboard", "Dashboard", "grid"], ["/staff/equipment", "Browse Equipment", "box"], ["/staff/requests", "My Requests", "inbox"], ["/staff/borrowed-items", "Borrowed Items", "return"], ["/staff/profile", "Profile", "people"]];
const esc = (value) => value ?? "—";
const prettyDate = (value) => value ? new Intl.DateTimeFormat("en-PH", { timeZone: "Asia/Manila", dateStyle: "medium" }).format(new Date(`${String(value).slice(0, 10)}T00:00:00+08:00`)) : "—";
const today = () => new Date().toISOString().slice(0, 10);

async function getJSON(url) {
  // Keep browser requests same-origin. The Next route handler forwards the
  // Flask session cookie server-to-server, so no browser CORS access is needed.
  const response = await fetch(proxy(url));
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "We could not load this information.");
  }
  return response.json();
}

function Icon({ name, size = 18 }) {
  const paths = {
    grid: "M4 4h6v6H4zm10 0h6v6h-6zM4 14h6v6H4zm10 0h6v6h-6z", box: "M4 7.5 12 3l8 4.5v9L12 21l-8-4.5zM4 7.5l8 4.5 8-4.5M12 12v9", people: "M16 20v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20m15-7a3 3 0 1 0 0-6m-6-1a3 3 0 1 1-6 0", plus: "M12 5v14M5 12h14", inbox: "M4 4h16v13H4zM4 13h4l2 3h4l2-3h4", return: "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 5 5v2", chart: "M4 19V5m0 14h17M8 16v-5m4 5V7m4 9v-7m4 7v-11", clock: "M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0", info: "M12 16v-5m0-3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0", logout: "M10 17l5-5-5-5m5 5H3m10-7h5a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-5", arrow: "m9 18 6-6-6-6", check: "m5 12 4 4L19 6"
  };
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.info} /></svg>;
}

function Notice() {
  const params = useSearchParams();
  const message = params.get("message");
  return message ? <p className="notice" role="status">{message}</p> : null;
}

function useSession() {
  const [session, setSession] = useState(null);
  useEffect(() => { getJSON("/api/session").then(setSession).catch(() => setSession({ authenticated: false })); }, []);
  return session;
}

function Shell({ children, session }) {
  const pathname = usePathname();
  const links = session?.role?.toLowerCase() === "admin" ? adminLinks : staffLinks;
  const initial = session?.full_name?.trim()?.charAt(0)?.toUpperCase() || "U";
  const dashboard = session?.role?.toLowerCase() === "admin" ? "/dashboard" : "/staff-dashboard";
  return <div className="shell"><aside className="sidebar"><a className="brand" href={dashboard}><span className="brand-mark"><Icon name="box" size={21} /></span><span>Barangay<span>Equip</span><small>Equipment borrowing portal</small></span></a><nav aria-label="Main navigation">{links.map(([href, label, icon]) => <a className={`nav-link ${pathname === href ? "active" : ""}`} href={href} key={href}><Icon name={icon} />{label}</a>)}</nav><div className="sidebar-bottom"><div className="sidebar-user"><span className="avatar">{initial}</span><span><strong>{session?.full_name}</strong><small>{session?.role}</small></span></div><a className="nav-link logout" href={proxy("/logout")}><Icon name="logout" />Sign out</a></div></aside><main className="content"><header className="top"><div><p className="eyebrow">{session?.role === "Admin" ? "Control center" : "Equipment portal"}</p><h1>{pageTitle(pathname)}</h1><p className="subtitle">Manage barangay resources with confidence.</p></div><div className="user"><span className="avatar">{initial}</span><span><strong>{session?.full_name}</strong><small>{session?.role} account</small></span></div></header><Notice />{children}</main></div>;
}

function pageTitle(path) {
  const titles = { "/dashboard": "Dashboard", "/staff-dashboard": "Dashboard", "/equipment": "Equipment Management", "/borrowers": "Borrower Management", "/borrowings": "New Borrowing Transaction", "/admin/borrowing-requests": "Borrowing Requests", "/returns": "Equipment Returns", "/reports": "Reports", "/audit-logs": "Audit Trail", "/about": "About", "/staff/equipment": "Browse Equipment", "/staff/requests": "My Borrowing Requests", "/staff/borrowed-items": "My Borrowed Items", "/staff/profile": "My Profile" };
  return titles[path] || "Barangay Equipment Borrowing System";
}

function AuthPage({ signup = false }) {
  const [showPassword, setShowPassword] = useState(false);
  return <main className="auth-page"><section className="auth-intro"><a className="brand auth-brand" href="/"><span className="brand-mark"><Icon name="box" size={21} /></span><span>Barangay<span>Equip</span></span></a><div><p className="eyebrow">Resource management, made simple</p><h1>Community equipment,<br /><em>properly managed.</em></h1><p>Track availability, process requests, and keep every transaction organized in one reliable workspace.</p></div><div className="auth-benefits"><span><Icon name="check" />Clear inventory visibility</span><span><Icon name="check" />Streamlined borrowing requests</span><span><Icon name="check" />Complete audit history</span></div></section><section className="auth-card"><div className="auth-card-heading"><p className="eyebrow">{signup ? "Create your account" : "Welcome back"}</p><h2>{signup ? "Join the portal" : "Sign in to continue"}</h2><p>{signup ? "Start requesting equipment for your barangay activities." : "Use your account to access the equipment portal."}</p></div><Notice /><form action={proxy(signup ? "/signup" : "/login")} method="post" className="form-stack">
    {signup && <><input name="full_name" placeholder="Full name" autoComplete="name" required /><input name="username" placeholder="Username" autoComplete="username" required /><input name="contact_number" placeholder="Contact number" autoComplete="tel" required /><input name="address" placeholder="Address" autoComplete="street-address" required /><input name="email" type="email" placeholder="Email" autoComplete="email" required /></>}
    {!signup && <input name="identity" placeholder="Username or email" autoComplete="username" required />}
    <label className="password-field"><input name="password" type={showPassword ? "text" : "password"} placeholder={signup ? "Create password" : "Password"} autoComplete={signup ? "new-password" : "current-password"} required /><button type="button" onClick={() => setShowPassword(!showPassword)}>{showPassword ? "Hide" : "Show"}</button></label>
    {signup && <input name="confirm_password" type={showPassword ? "text" : "password"} placeholder="Confirm password" autoComplete="new-password" required />}
    {signup && <small>Use 12+ characters with uppercase, lowercase, number, and symbol.</small>}
    <button className="button primary" type="submit">{signup ? "Create account" : "Sign in"}<Icon name="arrow" size={17} /></button>
    <p className="switch-line">{signup ? "Already have an account?" : "New to the portal?"} <a href={signup ? "/" : "/signup"}>{signup ? "Sign in" : "Create an account"}</a></p>
  </form></section></main>;
}

function StatCards({ cards }) { const icons = ["box", "check", "people", "inbox"]; return <section className="stat-grid">{cards.map(({ label, value }, index) => <article className="stat-card" key={label}><span className="stat-icon"><Icon name={icons[index] || "chart"} /></span><div><span>{label}</span><strong>{value}</strong></div></article>)}</section>; }

function Dashboard({ staff = false }) {
  const [stats, setStats] = useState(null);
  useEffect(() => { (async () => { try { const [equipment, requests, borrowed] = await Promise.all([getJSON(staff ? "/api/staff/equipment" : "/api/equipment"), staff ? getJSON("/api/staff/requests") : getJSON("/api/admin/borrowing-requests"), staff ? getJSON("/api/staff/borrowed-items") : getJSON("/api/borrowers")]); setStats(staff ? [{ label: "Available Equipment", value: equipment.reduce((n, item) => n + item.available_stock, 0) }, { label: "Pending Requests", value: requests.filter(x => x.status === "Pending").length }, { label: "Approved Requests", value: requests.filter(x => x.status === "Approved").length }, { label: "Currently Borrowed", value: borrowed.filter(x => ["Active", "Partially Returned"].includes(x.status)).length }] : [{ label: "Equipment Records", value: equipment.length }, { label: "Available Items", value: equipment.reduce((n, item) => n + item.available_stock, 0) }, { label: "Borrowers", value: borrowed.length }, { label: "Pending Requests", value: requests.filter(x => x.status === "Pending").length }]); } catch { setStats([]); } })(); }, [staff]);
  const actionHref = staff ? "/staff/equipment" : "/borrowings";
  return <><StatCards cards={stats || [{ label: "Loading", value: "…" }]} /><section className="welcome-panel"><div><p className="eyebrow">{staff ? "Ready when you are" : "Operations overview"}</p><h2>{staff ? "Find what you need for the community." : "Keep every item and transaction on track."}</h2><p>{staff ? "Browse available equipment and submit a borrowing request in a few clear steps." : "Review requests, issue equipment, and maintain a reliable inventory record from one place."}</p><a className="button" href={actionHref}>{staff ? "Browse equipment" : "Create transaction"}<Icon name="arrow" size={17} /></a></div><span className="welcome-icon"><Icon name={staff ? "box" : "chart"} size={52} /></span></section></>;
}

function Equipment() {
  const [rows, setRows] = useState([]), [query, setQuery] = useState({ search: "", status: "", sort: "name" }), [editing, setEditing] = useState(null);
  const load = () => getJSON(`/api/equipment?${new URLSearchParams(query)}`).then(setRows).catch(() => setRows([]));
  useEffect(load, [query.search, query.status, query.sort]);
  const item = editing || {};
  return <div className="two-col"><section className="panel table-wrap"><div className="toolbar"><input placeholder="Search equipment" value={query.search} onChange={e => setQuery({ ...query, search: e.target.value })} /><select value={query.status} onChange={e => setQuery({ ...query, status: e.target.value })}><option value="">All statuses</option><option>Available</option><option>Low Stock</option><option>Out of Stock</option></select><select value={query.sort} onChange={e => setQuery({ ...query, sort: e.target.value })}><option value="name">Equipment name</option><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="status">Status</option></select><button className="button secondary" onClick={() => setQuery({ search: "", status: "", sort: "name" })}>Clear</button></div><DataTable rows={rows} columns={[["Equipment", x => x.equipment_name], ["Category", x => x.category], ["Total", x => x.total_stock], ["Available", x => x.available_stock], ["Borrowed", x => x.borrowed_stock], ["Unit", x => x.unit_type], ["Status", x => <Status value={x.status} />]]} actions={x => <><button className="text-button" onClick={() => setEditing(x)}>Edit</button><form className="inline" action={proxy(`/equipment/${x.equipment_id}/delete`)} method="post" onSubmit={e => !confirm(`Delete “${x.equipment_name}”?`) && e.preventDefault()}><button className="text-button danger">Delete</button></form></>} /></section>
    <section className="panel"><h2>{editing ? `Edit: ${editing.equipment_name}` : "Add Equipment"}</h2><form className="form-stack" action={proxy(editing ? `/equipment/${editing.equipment_id}/edit` : "/equipment/add")} method="post"><input name="equipment_name" defaultValue={item.equipment_name} placeholder="Equipment name" required /><input name="category" defaultValue={item.category} placeholder="Category" required /><input name="total_stock" defaultValue={item.total_stock} type="number" min="0" placeholder="Total quantity" required /><input name="unit_type" defaultValue={item.unit_type} placeholder="Unit type" required /><button className="button">{editing ? "Update Equipment" : "Save Equipment"}</button>{editing && <button type="button" className="button secondary" onClick={() => setEditing(null)}>Cancel</button>}</form></section></div>;
}

function Borrowers() {
  const [rows, setRows] = useState([]), [search, setSearch] = useState(""), [editing, setEditing] = useState(null);
  useEffect(() => { getJSON(`/api/borrowers?search=${encodeURIComponent(search)}`).then(setRows).catch(() => setRows([])); }, [search]);
  const item = editing || {};
  return <div className="two-col"><section className="panel table-wrap"><div className="toolbar"><input placeholder="Search borrowers" value={search} onChange={e => setSearch(e.target.value)} /></div><DataTable rows={rows} columns={[["Borrower", x => x.full_name], ["Contact", x => x.contact_number], ["Address", x => x.address], ["Email", x => x.email]]} actions={x => <><button className="text-button" onClick={() => setEditing(x)}>Edit</button>{x.has_pending_request && <form className="inline" action={proxy(`/borrowers/${x.borrower_id}/approve-pending-request`)} method="post"><button className="text-button">Approve request</button></form>}<form className="inline" action={proxy(`/borrowers/${x.borrower_id}/delete`)} method="post" onSubmit={e => !confirm(`Delete ${x.full_name}?`) && e.preventDefault()}><button className="text-button danger">Delete</button></form></>} /></section><section className="panel"><h2>{editing ? "Edit Borrower" : "Add Borrower"}</h2><form className="form-stack" action={proxy(editing ? `/borrowers/${editing.borrower_id}/edit` : "/borrowers/add")} method="post"><input name="full_name" defaultValue={item.full_name} placeholder="Full name" required /><input name="contact_number" defaultValue={item.contact_number} placeholder="Contact number" required /><textarea name="address" defaultValue={item.address} placeholder="Address" required /><input name="email" defaultValue={item.email} type="email" placeholder="Email (optional)" /><button className="button">Save Borrower</button>{editing && <button className="button secondary" type="button" onClick={() => setEditing(null)}>Cancel</button>}</form></section></div>;
}

function Borrowings() {
  const [borrowers, setBorrowers] = useState([]), [equipment, setEquipment] = useState([]), [items, setItems] = useState([]), [selected, setSelected] = useState(""), [qty, setQty] = useState(1);
  useEffect(() => { Promise.all([getJSON("/api/borrowers"), getJSON("/api/borrowable-equipment")]).then(([b, e]) => { setBorrowers(b); setEquipment(e); }).catch(() => {}); }, []);
  const selectedItem = equipment.find(x => x.equipment_id === Number(selected));
  const add = () => { if (!selectedItem || !Number.isInteger(Number(qty)) || qty < 1 || qty > selectedItem.available_stock) return alert("Choose an available item and valid quantity."); if (items.some(x => x.equipment_id === selectedItem.equipment_id)) return alert("This equipment is already included."); setItems([...items, { ...selectedItem, quantity: Number(qty) }]); setQty(1); };
  return <form action={proxy("/borrowings/create")} method="post" className="form-stack" onSubmit={e => { if (!items.length) { e.preventDefault(); alert("Add at least one equipment item."); } }}><section className="panel grid-fields"><select name="borrower_id" required><option value="">Select borrower</option>{borrowers.map(x => <option value={x.borrower_id} key={x.borrower_id}>{x.full_name} — {x.contact_number}</option>)}</select><input name="expected_return_date" type="date" required /><textarea name="purpose_notes" placeholder="Purpose / notes (optional)" /></section><section className="panel grid-fields"><select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Select equipment</option>{equipment.map(x => <option value={x.equipment_id} key={x.equipment_id}>{x.equipment_name} ({x.available_stock} available)</option>)}</select><input type="number" min="1" max={selectedItem?.available_stock} value={qty} onChange={e => setQty(e.target.value)} /><button className="button" type="button" onClick={add}>Add item</button></section><input type="hidden" name="items" value={JSON.stringify(items.map(x => ({ equipment_id: x.equipment_id, quantity: x.quantity })))} /><section className="panel"><DataTable rows={items} columns={[["Equipment", x => x.equipment_name], ["Category", x => x.category], ["Available", x => x.available_stock], ["Quantity", x => x.quantity]]} actions={x => <button type="button" className="text-button danger" onClick={() => setItems(items.filter(i => i.equipment_id !== x.equipment_id))}>Remove</button>} empty="Add equipment to begin this transaction." /></section><button className="button">Borrow / Save Transaction</button></form>;
}

function Requests() {
  const [rows, setRows] = useState([]), [search, setSearch] = useState("");
  useEffect(() => { getJSON("/api/admin/borrowing-requests").then(setRows).catch(() => setRows([])); }, []);
  const filtered = rows.filter(x => `${x.borrower_name} ${x.equipment_name} ${x.borrowing_id}`.toLowerCase().includes(search.toLowerCase()));
  const action = (x, name, label) => <form className="inline" action={proxy(`/admin/borrowing-requests/${x.borrowing_id}/${name}`)} method="post" onSubmit={e => !confirm(`${label} request #${x.borrowing_id}?`) && e.preventDefault()}><button className="text-button">{label}</button></form>;
  return <section className="panel table-wrap"><div className="toolbar"><input placeholder="Search borrower, equipment, or ID" value={search} onChange={e => setSearch(e.target.value)} /></div><DataTable rows={filtered} columns={[["Request", x => `#${x.borrowing_id}`], ["Borrower", x => x.borrower_name], ["Equipment", x => x.equipment_name], ["Quantity", x => x.quantity_borrowed], ["Needed", x => prettyDate(x.date_needed)], ["Return", x => prettyDate(x.expected_return_date)], ["Status", x => <Status value={x.status} />]]} actions={x => x.status === "Pending" ? <>{action(x, "approve", "Approve")}{action(x, "reject", "Reject")}</> : x.status === "Approved" ? <>{action(x, "release", "Release")}{action(x, "reject", "Cancel")}</> : null} /></section>;
}

function Returns() {
  const [rows, setRows] = useState([]), [filters, setFilters] = useState({ search: "", status: "", date_field: "borrowed", start_date: "", end_date: "", sort: "newest" }), [loan, setLoan] = useState(null), [quantities, setQuantities] = useState({});
  useEffect(() => { getJSON(`/api/returnable-borrowings?${new URLSearchParams(filters)}`).then(setRows).catch(() => setRows([])); }, [filters]);
  const select = async (id) => { try { const next = await getJSON(`/api/borrowings/${id}/items`); setLoan(next); setQuantities({}); } catch { alert("Unable to load transaction."); } };
  return <><section className="panel"><div className="toolbar"><input placeholder="Loan ID, borrower, or equipment" value={filters.search} onChange={e => setFilters({ ...filters, search: e.target.value })} /><select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">All outstanding loans</option><option>Active</option><option>Partially Returned</option></select><select value={filters.sort} onChange={e => setFilters({ ...filters, sort: e.target.value })}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="borrower">Borrower name</option><option value="status">Status</option></select></div><DataTable rows={rows} columns={[["ID", x => `#${x.borrowing_id}`], ["Borrower", x => x.full_name], ["Borrowed", x => prettyDate(x.borrowed_at)], ["Expected Return", x => prettyDate(x.expected_return_date)], ["Status", x => x.status]]} actions={x => <button className="text-button" onClick={() => select(x.borrowing_id)}>Select</button>} /></section>{loan && <form className="panel form-stack" action={proxy("/returns/save")} method="post" onSubmit={e => { const items = Object.entries(quantities).filter(([, value]) => Number(value) > 0).map(([id, quantity]) => ({ borrowing_item_id: Number(id), quantity: Number(quantity) })); if (!items.length) { e.preventDefault(); alert("Enter a return quantity."); } }}><h2>Loan #{loan.borrowing_id} — {loan.full_name}</h2><input name="borrowing_id" type="hidden" value={loan.borrowing_id} /><input name="items" type="hidden" value={JSON.stringify(Object.entries(quantities).filter(([, value]) => Number(value) > 0).map(([id, quantity]) => ({ borrowing_item_id: Number(id), quantity: Number(quantity) })))} /><DataTable rows={loan.items} columns={[["Equipment", x => x.equipment_name], ["Borrowed", x => x.quantity_borrowed], ["Returned", x => x.quantity_returned], ["Remaining", x => x.remaining_quantity], ["Return quantity", x => <input type="number" min="0" max={x.remaining_quantity} disabled={!x.remaining_quantity} value={quantities[x.borrowing_item_id] || 0} onChange={e => setQuantities({ ...quantities, [x.borrowing_item_id]: e.target.value })} />]]} /><div className="toolbar"><input name="return_date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required /><textarea name="notes" placeholder="Notes (optional)" /><button className="button">Save Return</button><button type="button" className="button secondary" onClick={() => setLoan(null)}>Close</button></div></form>}</>;
}

function Reports() {
  const [filters, setFilters] = useState({ type: "inventory", search: "", status: "", start_date: "", end_date: "", borrower_id: "" }), [rows, setRows] = useState([]), [borrowers, setBorrowers] = useState([]);
  const load = () => getJSON(`/api/reports?${new URLSearchParams(filters)}`).then(setRows).catch(() => setRows([]));
  useEffect(() => { getJSON("/api/borrowers").then(setBorrowers).catch(() => {}); }, []); useEffect(load, [filters.type, filters.status]);
  return <><section className="panel toolbar"><select value={filters.type} onChange={e => setFilters({ ...filters, type: e.target.value })}>{[["inventory", "Equipment Inventory"], ["available", "Available Equipment"], ["active", "Active Borrowings"], ["current_borrowers", "Current Borrowers"], ["returned", "Returned Transactions"], ["history", "Borrower History"], ["transaction", "Borrowing Transaction"]].map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><input placeholder="Search" value={filters.search} onChange={e => setFilters({ ...filters, search: e.target.value })} /><select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">All statuses</option><option>Active</option><option>Partially Returned</option><option>Returned</option><option>Available</option><option>Low Stock</option><option>Out of Stock</option></select><select value={filters.borrower_id} onChange={e => setFilters({ ...filters, borrower_id: e.target.value })}><option value="">All borrowers</option>{borrowers.map(x => <option value={x.borrower_id} key={x.borrower_id}>{x.full_name}</option>)}</select><button className="button" onClick={load}>Preview</button><button className="button secondary" onClick={() => window.print()}>Print</button></section><section className="panel table-wrap"><h2>Generated report</h2><ObjectTable rows={rows} /></section></>;
}

function Audit() {
  const [filters, setFilters] = useState({ search: "", action: "", table: "", start_date: "", end_date: "" }), [rows, setRows] = useState([]);
  useEffect(() => { getJSON(`/api/audit-logs?${new URLSearchParams(filters)}`).then(setRows).catch(() => setRows([])); }, [filters]);
  return <section className="panel table-wrap"><div className="toolbar"><input placeholder="User, description, or record ID" value={filters.search} onChange={e => setFilters({ ...filters, search: e.target.value })} /><select value={filters.action} onChange={e => setFilters({ ...filters, action: e.target.value })}><option value="">All actions</option><option>CREATE</option><option>UPDATE</option><option>DELETE</option><option>RETURN</option></select><select value={filters.table} onChange={e => setFilters({ ...filters, table: e.target.value })}><option value="">All tables</option><option value="equipment">Equipment</option><option value="borrowers">Borrowers</option><option value="borrowings">Borrowings</option><option value="users">Users</option></select></div><DataTable rows={rows} columns={[["Date/Time", x => x.created_at ? new Date(x.created_at).toLocaleString() : "—"], ["User", x => x.full_name || x.username], ["Action", x => x.action], ["Table", x => x.table_name], ["Record", x => x.record_id], ["Description", x => x.description]]} /></section>;
}

function StaffEquipment() {
  const [rows, setRows] = useState([]), [search, setSearch] = useState(""), [selected, setSelected] = useState(null);
  useEffect(() => { getJSON("/api/staff/equipment").then(setRows).catch(() => setRows([])); }, []);
  const filtered = rows.filter(x => `${x.equipment_name} ${x.category}`.toLowerCase().includes(search.toLowerCase()));
  return <><section className="panel"><div className="toolbar"><input placeholder="Search equipment" value={search} onChange={e => setSearch(e.target.value)} /></div><div className="equipment-grid">{filtered.map(x => <article className="equipment-card" key={x.equipment_id}><span>{x.category}</span><h3>{x.equipment_name}</h3><p><strong>{x.available_stock}</strong> {x.unit_type} available</p><button className="button" onClick={() => setSelected(x)}>Request to Borrow</button></article>) || <p>No equipment found.</p>}</div></section>{selected && <form className="panel form-stack" action={proxy("/staff/requests/create")} method="post"><h2>Request: {selected.equipment_name}</h2><input name="equipment_id" type="hidden" value={selected.equipment_id} /><input name="quantity" type="number" min="1" max={selected.available_stock} placeholder={`Up to ${selected.available_stock}`} required /><label>Date needed <input name="date_needed" type="date" required /></label><label>Expected return <input name="expected_return_date" type="date" required /></label><textarea name="purpose_notes" placeholder="Purpose of borrowing" required /><textarea name="additional_notes" placeholder="Additional notes (optional)" /><div className="toolbar"><button className="button">Submit Request</button><button type="button" className="button secondary" onClick={() => setSelected(null)}>Cancel</button></div></form>}</>;
}

function StaffRows({ kind }) {
  const url = kind === "requests" ? "/api/staff/requests" : "/api/staff/borrowed-items";
  const [rows, setRows] = useState([]); useEffect(() => { getJSON(url).then(setRows).catch(() => setRows([])); }, [url]);
  const columns = kind === "requests" ? [["Request", x => `#${x.borrowing_id}`], ["Equipment", x => x.equipment_name], ["Quantity", x => x.quantity_borrowed], ["Purpose", x => x.purpose_notes], ["Date Needed", x => prettyDate(x.date_needed)], ["Expected Return", x => prettyDate(x.expected_return_date)], ["Status", x => <Status value={x.status} />]] : [["Loan", x => `#${x.borrowing_id}`], ["Equipment", x => x.equipment_name], ["Borrowed", x => x.quantity_borrowed], ["Returned", x => x.quantity_returned], ["Remaining", x => x.remaining_quantity], ["Expected Return", x => prettyDate(x.expected_return_date)], ["Status", x => <Status value={x.status} />]];
  return <section className="panel table-wrap"><DataTable rows={rows} columns={columns} /></section>;
}

function Profile({ session }) { return <section className="panel"><dl className="profile-grid"><dt>Full name</dt><dd>{session.full_name}</dd><dt>Username</dt><dd>{session.username}</dd><dt>Account role</dt><dd>{session.role}</dd></dl></section>; }

function About({ session }) { return <section className="panel"><h2>Barangay Equipment Borrowing System</h2><p className="subtitle">Version 1.0 - equipment, borrowers, borrowing, returns, reports, and audit trail.</p><p>This system helps barangay staff manage reusable equipment and borrowing transactions.</p><p><strong>Logged in as:</strong> {session.full_name}</p><a className="button" href={session.role?.toLowerCase() === "admin" ? "/dashboard" : "/staff-dashboard"}>Back to Dashboard</a></section>; }

function DataTable({ rows, columns, actions, empty = "No records found." }) { return <table><thead><tr>{columns.map(([name]) => <th key={name}>{name}</th>)}{actions && <th>Actions</th>}</tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={row.equipment_id || row.borrower_id || row.borrowing_item_id || row.audit_id || `${row.borrowing_id}-${row.equipment_name}-${index}`}>{columns.map(([name, render]) => <td key={name}>{render(row)}</td>)}{actions && <td className="row-actions">{actions(row)}</td>}</tr>) : <tr><td className="empty" colSpan={columns.length + (actions ? 1 : 0)}>{empty}</td></tr>}</tbody></table>; }
function ObjectTable({ rows }) { if (!rows.length) return <p className="empty">No report records found.</p>; const keys = Object.keys(rows[0]); return <table><thead><tr>{keys.map(key => <th key={key}>{key}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{keys.map(key => <td key={key}>{esc(row[key])}</td>)}</tr>)}</tbody></table>; }
function Status({ value }) { return <span className={`badge ${String(value || "").toLowerCase().replaceAll(" ", "-")}`}>{value}</span>; }

export default function Page() {
  const path = usePathname(), router = useRouter(), session = useSession();
  if (path === "/" || path === "/login.html") return <AuthPage />;
  if (path === "/signup" || path === "/signup.html") return <AuthPage signup />;
  if (!session) return <main className="loading">Loading…</main>;
  if (!session.authenticated) { router.replace("/"); return <main className="loading">Redirecting to login…</main>; }
  const content = path === "/dashboard" ? <Dashboard /> : path === "/staff-dashboard" ? <Dashboard staff /> : path === "/equipment" ? <Equipment /> : path === "/borrowers" ? <Borrowers /> : path === "/borrowings" ? <Borrowings /> : path === "/admin/borrowing-requests" ? <Requests /> : path === "/returns" ? <Returns /> : path === "/reports" ? <Reports /> : path === "/audit-logs" ? <Audit /> : path === "/about" ? <About session={session} /> : path === "/staff/equipment" ? <StaffEquipment /> : path === "/staff/requests" ? <StaffRows kind="requests" /> : path === "/staff/borrowed-items" ? <StaffRows kind="borrowed" /> : path === "/staff/profile" ? <Profile session={session} /> : <section className="panel"><p>This page is not available.</p></section>;
  return <Shell session={session}>{content}</Shell>;
}
