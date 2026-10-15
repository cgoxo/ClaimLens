import type { CaseSummary } from "../api/types";
import { askPermission, finishedText, notifyFinished } from "./notify";

const ready: CaseSummary = { id: "3f2a91", status: "READY", risk: "high", score: 100, created_at: "", progress: null,
  findings_count: 4, unseen: true };

function stubNotification(permission: NotificationPermission) {
  const created: { title: string; onclick: (() => void) | null }[] = [];
  const Fake = vi.fn(function (this: { title: string; onclick: (() => void) | null }, title: string) {
    this.title = title;
    this.onclick = null;
    created.push(this);
  }) as unknown as typeof Notification;
  Object.assign(Fake, { permission, requestPermission: vi.fn(async () => permission) });
  vi.stubGlobal("Notification", Fake);
  return { Fake, created };
}

function visibility(state: "hidden" | "visible") {
  Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
}

afterEach(() => {
  vi.unstubAllGlobals();
  visibility("visible");
});

test("text for ready and failed cases", () => {
  expect(finishedText(ready)).toBe("Case 3f2a91 ready: HIGH risk, 4 findings");
  expect(finishedText({ ...ready, status: "FAILED" })).toBe("Case 3f2a91 failed");
});

test("hidden tab with permission shows one system notification that opens the case", () => {
  const { created } = stubNotification("granted");
  visibility("hidden");
  const onClick = vi.fn();
  expect(notifyFinished(ready, onClick)).toBe(true);
  expect(created).toHaveLength(1);
  expect(created[0].title).toBe("Case 3f2a91 ready: HIGH risk, 4 findings");
  created[0].onclick!();
  expect(onClick).toHaveBeenCalled();
});

test("visible tab shows no notification", () => {
  const { created } = stubNotification("granted");
  expect(notifyFinished(ready, vi.fn())).toBe(false);
  expect(created).toHaveLength(0);
});

test("denied permission shows no notification", () => {
  stubNotification("denied");
  visibility("hidden");
  expect(notifyFinished(ready, vi.fn())).toBe(false);
});

test("no Notification API never throws", () => {
  vi.stubGlobal("Notification", undefined);
  visibility("hidden");
  expect(notifyFinished(ready, vi.fn())).toBe(false);
  expect(() => askPermission()).not.toThrow();
});

test("asks only when the user hasn't decided", () => {
  const { Fake } = stubNotification("default");
  askPermission();
  expect(Fake.requestPermission).toHaveBeenCalledTimes(1);
  stubNotification("denied");
  askPermission();
  expect((Notification as typeof Fake).requestPermission).not.toHaveBeenCalled();
});

test("text for a rejected case", () => {
  expect(finishedText({ ...ready, status: "REJECTED" })).toBe("Case 3f2a91 can't be analysed: some files aren't insurance documents");
});
