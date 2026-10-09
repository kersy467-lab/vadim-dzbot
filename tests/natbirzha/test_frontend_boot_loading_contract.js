const assert = require('assert');
const fs = require('fs');
const path = require('path');

const read = (relativePath) => fs.readFileSync(
  path.join(__dirname, '../../', relativePath),
  'utf8',
);

const app = read('frontend/natbirzha/js/app.js');
const bankruptcyGate = read('frontend/natbirzha/js/bankruptcy_gate.js');

const scopeIndex = app.indexOf('beginNavigationScope();', app.indexOf('export async function initApp'));
const monitorIndex = app.indexOf('startBankruptcyMonitor({', scopeIndex);
const renderIndex = app.indexOf('await renderCurrentScreen();', monitorIndex);
assert(
  scopeIndex !== -1 && monitorIndex > scopeIndex && renderIndex > monitorIndex
    && app.slice(monitorIndex - 8, monitorIndex).includes('void'),
  'the initial screen should render without waiting for the bankruptcy status request',
);

const scheduleIndex = bankruptcyGate.indexOf('monitorTimer = window.setInterval');
const firstCheckIndex = bankruptcyGate.indexOf('await checkBankruptcy(options)');
assert(
  scheduleIndex !== -1 && firstCheckIndex !== -1 && scheduleIndex < firstCheckIndex,
  'the periodic bankruptcy check should be scheduled before the initial request completes',
);
assert(
  bankruptcyGate.includes('if (bankruptcyCheckInFlight) return;')
    && bankruptcyGate.includes('String(currentCompanyId) !== String(companyId)'),
  'bankruptcy status polling should not overlap requests or apply a stale result to a different company',
);
console.log('Frontend initial-screen loading contract verified.');
