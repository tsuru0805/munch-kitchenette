// Expo config for the kitchen page (web only; no native build is configured here).
// KITCHENETTE_PAGE_BASE = the path the page is served under. The server serves it at /page, which is
// what the build committed in src/kitchenette/page/ uses; set it only to host the files somewhere else.
const base = (process.env.KITCHENETTE_PAGE_BASE ?? "/page").replace(/\/+$/, "");

module.exports = {
  expo: {
    name: "Kitchenette",
    slug: "kitchenette-page",
    version: "0.2.0",
    orientation: "portrait",
    userInterfaceStyle: "light",
    platforms: ["web"],
    web: { output: "single", bundler: "metro", name: "Kitchenette", shortName: "Kitchenette", lang: "zh", themeColor: "#fbf6ef", backgroundColor: "#fbf6ef" },
    experiments: { baseUrl: base },
  },
};
