import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider, useToast } from "./Toast";

function Trigger({ onClick }: { onClick?: () => void }) {
  const toast = useToast();
  return <button onClick={() => toast("Case c1 ready: LOW risk, 0 findings", onClick)}>go</button>;
}

afterEach(() => vi.useRealTimers());

test("a toast shows and goes away after 6 s", () => {
  vi.useFakeTimers();
  render(<ToastProvider><Trigger /></ToastProvider>);
  act(() => screen.getByText("go").click());
  expect(screen.getByRole("status")).toHaveTextContent("Case c1 ready: LOW risk, 0 findings");
  act(() => { vi.advanceTimersByTime(6000); });
  expect(screen.queryByText("Case c1 ready: LOW risk, 0 findings")).toBeNull();
});

test("clicking a toast runs its action", async () => {
  const onClick = vi.fn();
  render(<ToastProvider><Trigger onClick={onClick} /></ToastProvider>);
  await userEvent.click(screen.getByText("go"));
  await userEvent.click(screen.getByRole("button", { name: "Case c1 ready: LOW risk, 0 findings" }));
  expect(onClick).toHaveBeenCalled();
});
