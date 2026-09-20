const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log('=== [1/3] Testing ege_paronyms_data.js data integrity ===');
const pData = require('../frontend/js/ege_paronyms_data.js');

assert(pData.groups && Array.isArray(pData.groups), 'groups must be an array');
assert(pData.groups.length === 144, `Expected exactly 144 paronym groups from FIPI 2026, got ${pData.groups.length}`);
console.log(`Verified ${pData.groups.length} paronym groups from FIPI 2026 кодификатор!`);

assert(pData.questions && Array.isArray(pData.questions), 'questions must be an array');
assert(pData.questions.length === 144, `Expected 144 training questions, got ${pData.questions.length}`);
console.log(`Verified ${pData.questions.length} context training questions!`);

assert(pData.letters && Array.isArray(pData.letters), 'letters must be an array');
assert(pData.letters.includes('Все'), 'letters must include "Все"');
assert(pData.letters.length >= 15, 'letters must cover the Russian alphabet');

// Validate each paronym group
pData.groups.forEach((g, idx) => {
  assert(g.id, `Group at ${idx} missing id`);
  assert(g.title, `Group ${g.id} missing title`);
  assert(g.letter, `Group ${g.id} missing letter`);
  assert(Array.isArray(g.words) && g.words.length >= 2, `Group ${g.id} (${g.title}) must have at least 2 words`);

  g.words.forEach(w => {
    assert(w.word && typeof w.word === 'string', `Group ${g.id} has invalid word`);
    assert(w.meaning && typeof w.meaning === 'string', `Word ${w.word} missing meaning`);
    assert(Array.isArray(w.examples) && w.examples.length >= 1, `Word ${w.word} must have examples`);
  });
});

// Validate each question
pData.questions.forEach((q, idx) => {
  assert(q.id, `Question at ${idx} missing id`);
  assert(q.sentence && q.sentence.includes('_____'), `Question ${q.id} missing _____ blank in sentence: ${q.sentence}`);
  assert(Array.isArray(q.options) && q.options.length >= 2, `Question ${q.id} must have >= 2 options`);
  assert(q.correct && q.options.includes(q.correct), `Question ${q.id}: correct answer '${q.correct}' not in options [${q.options.join(', ')}]`);
  assert(q.explanation && q.explanation.length > 5, `Question ${q.id} missing explanation`);
});

console.log('All 144 paronym groups and 144 test questions passed structural validation!');

console.log('=== [2/3] Testing HTML script import and ege_data.js availability ===');
const html = fs.readFileSync(path.join(__dirname, '../frontend/index.html'), 'utf-8');
assert(html.includes('/static/js/ege_paronyms_data.js'), 'index.html must import ege_paronyms_data.js');

const egeData = require('../frontend/js/ege_data.js');
const rus = egeData.subjects.find(s => s.id === 'russian');
const task5 = rus.tasks.find(t => t.number === 5);
assert(task5 && task5.available === true, 'Task 5 in ege_data.js must have available: true');
console.log('Task 5 is enabled in ege_data.js and loaded in index.html!');

console.log('=== [3/3] Testing ege.js with Task 5 in mock DOM environment ===');
const mockWindow = {
  EGE_DATA: egeData,
  PARONYMS_DATA: pData,
  Telegram: {
    WebApp: {
      HapticFeedback: {
        impactOccurred: () => {},
        notificationOccurred: () => {},
        selectionChanged: () => {}
      }
    }
  }
};
global.window = mockWindow;
global.document = {
  getElementById: (id) => ({
    innerHTML: '',
    classList: { add: () => {}, remove: () => {} }
  }),
  querySelectorAll: () => []
};

const egeScript = fs.readFileSync(path.join(__dirname, '../frontend/js/ege.js'), 'utf-8');
eval(egeScript);

assert(typeof mockWindow.EGE.selectTask === 'function', 'window.EGE.selectTask must be defined');
assert(typeof mockWindow.EGE.setPLetterFilter === 'function', 'window.EGE.setPLetterFilter must be defined');
assert(typeof mockWindow.EGE.onParonymSearch === 'function', 'window.EGE.onParonymSearch must be defined');
assert(typeof mockWindow.EGE.startPQuiz === 'function', 'window.EGE.startPQuiz must be defined');
assert(typeof mockWindow.EGE.answerPQuestion === 'function', 'window.EGE.answerPQuestion must be defined');
assert(typeof mockWindow.EGE.nextPQuestion === 'function', 'window.EGE.nextPQuestion must be defined');
assert(typeof mockWindow.EGE.resetPQuiz === 'function', 'window.EGE.resetPQuiz must be defined');

// Test task switching to Task 5
mockWindow.EGE.selectTask(5);
console.log('Switched to Task 5 (Paronyms) successfully!');

// Test quiz start and answer
mockWindow.EGE.startPQuiz(false);
mockWindow.EGE.answerPQuestion(pData.questions[0].options[0]);
mockWindow.EGE.nextPQuestion();
console.log('Task 5 quiz execution verified!');

console.log('\n🎉 ALL TASK 5 PARONYM TESTS PASSED SUCCESSFULLY! 🚀');
