const fs = require('fs');
const path = require('path');
const assert = require('assert');

const root = path.join(__dirname, '..');
const dealScreen = fs.readFileSync(path.join(root, 'frontend/natbirzha/js/screens/market_deals.js'), 'utf8');
const jointScreenPath = path.join(root, 'frontend/natbirzha/js/screens/market_joint_factories.js');
const api = fs.readFileSync(path.join(root, 'frontend/natbirzha/js/api.js'), 'utf8');

assert(dealScreen.includes('data-view="joint-factories"'), 'Deals must link to a dedicated joint factories section');
assert(dealScreen.includes('renderMarketJointFactories'), 'Deals must route into the independent joint-factories screen');
assert(fs.existsSync(jointScreenPath), 'joint factories must have an independent screen module');
const jointScreen = fs.readFileSync(jointScreenPath, 'utf8');
assert(jointScreen.includes('Совместные заводы'), 'joint factories screen must have a Russian title');
assert(jointScreen.includes('dedicated') || jointScreen.includes('Отдельный слот'), 'screen must explain the separate joint-factory slot');
assert(jointScreen.includes('Без текущих расходов') || jointScreen.includes('без текущих расходов'), 'screen must explain zero operating costs');
assert(jointScreen.includes('contribution_sides') && jointScreen.includes('Взносы каждой компании'), 'joint proposals must show both owners’ separate cash and resource contributions');
assert(api.includes('getJointFactories:') && api.includes('getJointFactoryPartners:'), 'API client must load projects and compatible partners');
assert(api.includes('createJointFactoryProposal:') && api.includes('acceptJointFactoryProposal:'), 'API client must create and accept proposals');
assert(api.includes('requestJointFactoryUpgrade:') && api.includes('claimJointFactory:'), 'API client must support upgrade requests and owner claims');

console.log('Joint factory frontend contract passed.');
