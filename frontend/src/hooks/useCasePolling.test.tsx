import { act, renderHook } from "@testing-library/react";
import { ApiError, type Client } from "../api/client";
import type { Case, Status } from "../api/types";
import { sampleCase } from "../test/sampleCase";
import { useCasePolling } from "./useCasePolling";

const withStatus = (status: Status): Case => ({ ...sampleCase, status });

function fakeClient(...results: (Case | Error)[]) {
  const getCase = vi.fn(async () => {
    const next = results.length > 1 ? results.shift()! : results[0];
    if (next instanceof Error) throw next;
    return next;
  });
  return { client: { getCase } as unknown as Client, getCase };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const tick = async (ms = 2000) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

test("polls while running and stops at READY", async () => {
  const { client, getCase } = fakeClient(withStatus("CHECKING"), withStatus("PROVING"), withStatus("READY"));
  const { result } = renderHook(() => useCasePolling("c1", client));
  await tick(0);
  expect(result.current.data?.status).toBe("CHECKING");
  await tick();
  await tick();
  expect(result.current.data?.status).toBe("READY");
  await tick();
  await tick();
  expect(getCase).toHaveBeenCalledTimes(3);
});

test("stops at FAILED", async () => {
  const { client, getCase } = fakeClient(withStatus("FAILED"));
  renderHook(() => useCasePolling("c1", client));
  await tick(0);
  await tick();
  expect(getCase).toHaveBeenCalledTimes(1);
});

test("no calls after unmount", async () => {
  const { client, getCase } = fakeClient(withStatus("READING"));
  const { unmount } = renderHook(() => useCasePolling("c1", client));
  await tick(0);
  unmount();
  await tick();
  await tick();
  expect(getCase).toHaveBeenCalledTimes(1);
});

test("a 404 stops polling and sets the error", async () => {
  const { client, getCase } = fakeClient(new ApiError(404, "Case not found"));
  const { result } = renderHook(() => useCasePolling("c1", client));
  await tick(0);
  await tick();
  expect(result.current.error?.status).toBe(404);
  expect(getCase).toHaveBeenCalledTimes(1);
});

test("5 network failures in a row set connectionLost; a success clears it", async () => {
  const err = new TypeError("Failed to fetch");
  const { client } = fakeClient(err, err, err, err, err, withStatus("CHECKING"));
  const { result } = renderHook(() => useCasePolling("c1", client));
  await tick(0);
  for (let i = 0; i < 4; i++) await tick();
  expect(result.current.connectionLost).toBe(true);
  await tick();
  expect(result.current.connectionLost).toBe(false);
  expect(result.current.data?.status).toBe("CHECKING");
});
