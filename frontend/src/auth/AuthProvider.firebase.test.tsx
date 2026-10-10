import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./AuthProvider";

vi.mock("./firebase", () => {
  throw new Error("Failed to fetch dynamically imported module");
});

function Probe() {
  const a = useAuth();
  return <span data-testid="s">{a.status}|{a.error ?? ""}</span>;
}

test("if sign-in code fails to load, the user is told instead of waiting forever", async () => {
  render(<AuthProvider mode="firebase"><Probe /></AuthProvider>);
  await waitFor(() => expect(screen.getByTestId("s")).toHaveTextContent(/^signedOut\|Couldn't load sign-in/));
});
