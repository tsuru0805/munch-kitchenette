const path = require("node:path");
const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);
// The kitchen picture in its three lights and the pieces put back onto it are the pictures of the
// online demo (docs/play/img/): the page uses them from there rather than keeping a second copy.
// The cook's chore clips are the sprite pack of the cooking card (assets/clawd/), used from there too.
config.watchFolders = [
  ...(config.watchFolders ?? []),
  path.resolve(__dirname, "..", "..", "docs", "play", "img"),
  path.resolve(__dirname, "..", "..", "assets", "clawd"),
];

module.exports = config;
