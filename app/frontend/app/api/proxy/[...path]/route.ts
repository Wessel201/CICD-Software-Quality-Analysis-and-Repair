import type { NextRequest } from "next/server";

const UPSTREAM_API_BASE = process.env.API_BASE || "http://localhost:8000";
const UPSTREAM_API_KEY = process.env.API_KEY || "";

function buildUpstreamUrl(pathSegments: string[], search: string): string {
  const cleanBase = UPSTREAM_API_BASE.endsWith("/")
    ? UPSTREAM_API_BASE.slice(0, -1)
    : UPSTREAM_API_BASE;
  const path = pathSegments.join("/");
  return `${cleanBase}/${path}${search}`;
}

async function proxyRequest(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const startedAt = Date.now();

  if (!UPSTREAM_API_KEY) {
    console.error(
      JSON.stringify({
        event: "frontend_proxy_error",
        method: request.method,
        path: request.nextUrl.pathname,
        status: 500,
        message: "Missing API_KEY for upstream proxy",
      }),
    );
    return Response.json(
      { detail: "Server is missing API_KEY for upstream API proxy." },
      { status: 500 },
    );
  }

  const { path } = await context.params;
  const upstreamUrl = buildUpstreamUrl(path, request.nextUrl.search);

  console.info(
    JSON.stringify({
      event: "frontend_proxy_request",
      method: request.method,
      path: request.nextUrl.pathname,
      search: request.nextUrl.search,
      upstream_path: `/${path.join("/")}`,
    }),
  );

  const headers = new Headers(request.headers);
  headers.set("x-api-key", UPSTREAM_API_KEY);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  const body = request.method === "GET" || request.method === "HEAD"
    ? undefined
    : await request.arrayBuffer();

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });
  } catch (error) {
    console.error(
      JSON.stringify({
        event: "frontend_proxy_upstream_unreachable",
        method: request.method,
        path: request.nextUrl.pathname,
        upstream_url: upstreamUrl,
        duration_ms: Date.now() - startedAt,
        message: error instanceof Error ? error.message : String(error),
      }),
    );

    return Response.json(
      { detail: "Upstream API is unreachable from the frontend proxy." },
      { status: 502 },
    );
  }

  console.info(
    JSON.stringify({
      event: "frontend_proxy_response",
      method: request.method,
      path: request.nextUrl.pathname,
      status: upstreamResponse.status,
      duration_ms: Date.now() - startedAt,
    }),
  );

  const responseHeaders = new Headers(upstreamResponse.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");
  responseHeaders.set("cache-control", "no-store, no-cache, must-revalidate, max-age=0");
  responseHeaders.set("pragma", "no-cache");
  responseHeaders.set("expires", "0");

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders,
  });
}

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  return proxyRequest(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  return proxyRequest(request, context);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  return proxyRequest(request, context);
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  return proxyRequest(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  return proxyRequest(request, context);
}
