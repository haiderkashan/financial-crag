import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Paths requiring active analyst authentication
const PROTECTED_PREFIXES = ["/dashboard", "/workspace", "/agent"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const accessToken = request.cookies.get("access_token")?.value;
  const refreshToken = request.cookies.get("refresh_token")?.value;
  const hasSession = Boolean(accessToken || refreshToken);

  const isProtectedRoute = PROTECTED_PREFIXES.some((prefix) =>
    pathname.startsWith(prefix)
  );

  // 1. Redirect unauthenticated users away from protected routes to /login
  if (isProtectedRoute && !hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 2. Redirect already-authenticated users trying to access /login to /dashboard
  if (pathname === "/login" && hasSession) {
    const dashboardUrl = new URL("/dashboard", request.url);
    return NextResponse.redirect(dashboardUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/workspace/:path*",
    "/agent/:path*",
    "/login",
  ],
};
