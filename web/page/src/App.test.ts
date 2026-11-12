// Start-up choices: what the address may say, and whose kitchen opens first.
jest.mock("./KitchenPage", () => ({ KitchenPage: () => null }));

import { firstRole, readQuery } from "./App";
import type { About } from "./kitchen/kitchenApi";

const about: About = { roles: ["aster", "birch"], defaultRole: "aster", stamina: true, satiety: true, devClock: false, hungryBelow: 30, buyMaxItems: 5 };

test("the address may name a role and a server, never a token", () => {
  expect(readQuery("?who=birch&api=https%3A%2F%2Fkitchen.example.com%2Fanything")).toEqual({ who: "birch", api: "https://kitchen.example.com" });
  expect(readQuery("?api=javascript:alert(1)")).toEqual({ who: null, api: "" });
  expect(readQuery("")).toEqual({ who: null, api: "" });
});

test("whose kitchen opens: the one asked for, else the last one, else the default; only roles the server lists", () => {
  expect(firstRole(about, "birch", "aster")).toBe("birch");
  expect(firstRole(about, "nobody", "birch")).toBe("birch");
  expect(firstRole(about, null, "gone")).toBe("aster");
});
