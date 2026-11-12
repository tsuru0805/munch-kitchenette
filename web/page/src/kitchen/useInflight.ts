// Subscribes a component to an in-flight lock (the locks live in fridgeApi and outlive a closed sheet).
import { useSyncExternalStore } from "react";
import { isInflight, subscribeInflight } from "./fridgeApi";

export function useInflight(key: string): boolean {
  return useSyncExternalStore(subscribeInflight, () => isInflight(key), () => isInflight(key));
}
