const BACKEND = process.env.FLASK_API_URL || (
  process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:5000"
);

async function proxy(request, { params }) {
  if (!BACKEND) {
    return Response.json(
      { error: "The API service is not configured." },
      { status: 503 }
    );
  }
  const target = new URL(`/${params.path.join("/")}`, BACKEND);
  target.search = new URL(request.url).search;
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");
  const response = await fetch(target, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    redirect: "manual",
    // Required by Node when forwarding a streaming request body.
    duplex: "half"
  });
  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  return new Response(response.body, { status: response.status, headers: responseHeaders });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
