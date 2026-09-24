const fs = require('fs');
const path = require('path');
const assert = require('assert');

const catalog = fs.readFileSync(
  path.join(__dirname, '../../frontend/natbirzha/js/screens/catalog.js'),
  'utf-8',
);

assert(
  /Цена строительства[^\n]*build_cost/.test(catalog),
  'factory construction prices must remain visible even when a factory is locked',
);
console.log('Future factory prices are visible in the catalog.');
