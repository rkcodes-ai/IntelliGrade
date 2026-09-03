import { describe, expect, it } from "vitest";

import { router } from "@/routes";

function collectPaths(routes: typeof router.routes): string[] {
  return routes.flatMap((route) => [
    ...(route.path ? [route.path] : []),
    ...(route.children ? collectPaths(route.children as typeof router.routes) : []),
  ]);
}

describe("router", () => {
  it("registers the expected top-level and nested routes", () => {
    const paths = collectPaths(router.routes);

    expect(paths).toEqual(
      expect.arrayContaining([
        "/",
        "/login",
        "/forgot-password",
        "/reset-password",
        "/unauthorized",
        "/dashboard",
        "profile",
        "sessions",
        "*",
      ]),
    );
  });

  it("guards the /dashboard subtree behind ProtectedRoute", () => {
    const protectedNode = router.routes.find((route) =>
      (route.children ?? []).some((child) => child.path === "/dashboard"),
    );
    expect(protectedNode).toBeDefined();
    expect(protectedNode?.path).toBeUndefined();
  });
});
