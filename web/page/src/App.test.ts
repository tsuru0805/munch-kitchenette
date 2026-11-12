// Start-up choices: what the address may say, and whose kitchen opens first.
jest.mock("./KitchenPage", () => ({ KitchenPage: () => null }));

import { firstRole, readQuery, unknownRoleError } from "./App";
import type { About } from "./kitchen/kitchenApi";

const about: About = { roles: ["aster", "birch"], defaultRole: "aster", stamina: true, satiety: true, devClock: false, hungryBelow: 30, buyMaxItems: 5 };

test("the address may name a role and a server, never a token", () => {
  expect(readQuery("?who=birch&api=https%3A%2F%2Fkitchen.example.com%2Fanything")).toEqual({ who: "birch", api: "https://kitchen.example.com" });
  expect(readQuery("?api=javascript:alert(1)")).toEqual({ who: null, api: "" });
  expect(readQuery("")).toEqual({ who: null, api: "" });
});

describe("whose kitchen opens: only roles the server lists", () => {
  test("the one asked for, when the server lists it", () => {
    expect(firstRole(about, "birch", "aster")).toEqual({ role: "birch", unknown: null });
  });
  test("asked for but not listed: the default role (not the one opened last time), and the name is passed on to be said", () => {
    expect(firstRole(about, "nobody", "birch")).toEqual({ role: "aster", unknown: "nobody" });
  });
  test("nothing asked for: the one opened last time if it is still listed, else the default", () => {
    expect(firstRole(about, null, "birch")).toEqual({ role: "birch", unknown: null });
    expect(firstRole(about, null, "gone")).toEqual({ role: "aster", unknown: null });
    expect(firstRole(about, null, "")).toEqual({ role: "aster", unknown: null });
  });
  test("what a host is told about a role that does not exist", () => {
    expect(unknownRoleError("nobody", about)).toBe('unknown role "nobody": the kitchen server lists "aster", "birch"');
  });
});
