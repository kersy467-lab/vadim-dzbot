#!/usr/bin/env node
/**
 * build_rpg.js — Bundles modular RPG files from frontend/js/rpg_modules/
 * into the unified production build at frontend/js/rpg.js.
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const MODULES_DIR = path.join(__dirname, '..', 'frontend', 'js', 'rpg_modules');
const OUTPUT_FILE = path.join(__dirname, '..', 'frontend', 'js', 'rpg.js');

const files = fs.readdirSync(MODULES_DIR).filter(f => f.endsWith('.js')).sort();

console.log(`[RPG Builder] Bundling ${files.length} modules from ${MODULES_DIR}...`);

let bundle = [];
let totalLines = 0;

for (const file of files) {
  const filePath = path.join(MODULES_DIR, file);
  const content = fs.readFileSync(filePath, 'utf-8');
  const lineCount = content.split('\n').length;
  console.log(`  + ${file} (${lineCount} lines)`);
  bundle.push(content);
  totalLines += lineCount;
}

const joined = bundle.join('\n');
fs.writeFileSync(OUTPUT_FILE, joined, 'utf-8');
console.log(`[RPG Builder] Successfully wrote ${totalLines} lines to ${OUTPUT_FILE}`);

// Validate syntax
try {
  execSync(`node -c "${OUTPUT_FILE}"`, { stdio: 'inherit' });
  console.log('[RPG Builder] Syntax validation PASSED! OK.');
} catch (e) {
  console.error('[RPG Builder] Syntax validation FAILED!', e.message);
  process.exit(1);
}
