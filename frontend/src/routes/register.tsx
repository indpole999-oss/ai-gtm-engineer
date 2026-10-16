import { createFileRoute } from "@tanstack/react-router";
import { LoginPage } from "./login";

export const Route = createFileRoute("/register")({
  ssr: false,
  head: () => ({
    meta: [{ title: "Create account | GAPS AI" }, { name: "robots", content: "noindex" }],
  }),
  component: () => <LoginPage initialMode="register" />,
});
