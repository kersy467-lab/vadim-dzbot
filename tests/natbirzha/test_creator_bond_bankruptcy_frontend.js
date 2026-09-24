const fs = require('fs');
const path = require('path');
const assert = require('assert');

const root = path.join(__dirname, '../..');
const creator = fs.readFileSync(path.join(root, 'frontend/natbirzha/js/screens/creator.js'), 'utf8');
const bondApi = fs.readFileSync(path.join(root, 'frontend/natbirzha/js/screens/creator_bond_api.js'), 'utf8');

assert(creator.includes('bankrupt-bond-btn') && creator.includes('Банкрот'),
  'the government bond list must provide a bankruptcy action beside each issue');
assert(creator.includes('declareCreatorBondBankruptcy') && creator.includes('30%') && creator.includes('70%'),
  'the action must confirm the 30% compensation and 70% principal write-off');
assert(bondApi.includes('/creator/bonds/${id}/bankrupt')
  && bondApi.includes("method: 'POST'")
  && bondApi.includes("'Idempotency-Key'"),
  'the creator action must call the authenticated idempotent bankruptcy endpoint');
assert(!fs.readFileSync(path.join(root, 'frontend/natbirzha/js/api.js'), 'utf8').includes('bankruptCreatorBond'),
  'the shared API module remains unchanged');

console.log('Creator bond bankruptcy UI contract: PASS');
