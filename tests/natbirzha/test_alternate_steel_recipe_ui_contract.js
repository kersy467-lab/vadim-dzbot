const fs = require('fs');
const path = require('path');
const assert = require('assert');

const production = fs.readFileSync(
  path.join(__dirname, '../../frontend/natbirzha/js/screens/production.js'),
  'utf8',
);

assert(production.includes('factory-recipe-select'), 'production cards must expose a manual recipe selector');
assert(production.includes('state.selectedRecipes'), 'manual recipe choice must survive screen rerenders during the visit');
assert(production.includes('data-recipe-id='), 'selector options must identify the selected recipe');
assert(production.includes('NatAPI.triggerProduction(factory.id, selected.id)'),
  'the selected recipe id must be sent to the existing start API');
const currentRecipeIndex = production.search(/const selected = (?:factory|f)\.current_recipe/);
const manualChoiceIndex = production.search(/state\.selectedRecipes\?\.\[(?:factory|f)\.id\]/);
assert(currentRecipeIndex >= 0 && manualChoiceIndex > currentRecipeIndex,
  'a running cycle must display its server-authoritative recipe before a pending manual choice');
assert(production.includes('event.target.closest(\'select\')'),
  'using the dropdown must not bubble into the factory-card start action');
assert(production.includes('if (enable) delete state.selectedRecipes[factoryId]'),
  'automation must clear a manual-only choice and keep its default recipe behavior');

console.log('Alternate steel recipe selector contract verified.');
