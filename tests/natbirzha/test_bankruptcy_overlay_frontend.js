const fs = require('fs');
const path = require('path');
const assert = require('assert');

const root = path.join(__dirname, '../../frontend/natbirzha/js');
const gate = fs.readFileSync(path.join(root, 'bankruptcy_gate.js'), 'utf8');
const app = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const api = fs.readFileSync(path.join(root, 'api.js'), 'utf8');

assert(gate.includes('ВЫ БАНКРОТ'), 'bankruptcy must open a full-screen warning');
assert(gate.includes('Начать заново'), 'bankruptcy warning must offer a fresh restart');
assert(gate.includes('Продолжить'), 'bankruptcy warning must allow continuing after liquidation');
assert(gate.includes('+100 000'), 'restart action must disclose its cash grant');
assert(app.includes('startBankruptcyMonitor'), 'the app must check bankruptcy before normal play');
assert(api.includes('/api/natbirzha/bankruptcy/restart'), 'the restart button must call the authenticated restart API');

console.log('Bankruptcy full-screen recovery UI contract: PASS');
