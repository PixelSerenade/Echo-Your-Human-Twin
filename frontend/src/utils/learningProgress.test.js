import assert from 'node:assert/strict';
import { learningProgressFromTurns, nextLearningProgress } from './learningProgress.js';

let progress = nextLearningProgress(null, [], 'Quiz me on this PDF');
assert.deepEqual(progress, { active: true, answered: 0, target: 5 });
progress = nextLearningProgress(progress, [
  { role: 'assistant', content: 'Question one: What does the first section explain?' },
], 'It explains how cells use energy.');
assert.equal(progress.answered, 1, 'increments after answering a quiz question');
assert.equal(progress.target, 5);

const invited = nextLearningProgress(null, [
  { role: 'assistant', content: 'Are you ready to dive into the first word?' },
], 'yes');
assert.deepEqual(invited, { active: true, answered: 0, target: 5 }, 'starts when the user accepts a practice invitation');

const clarification = nextLearningProgress({ active: true, answered: 0, target: 5 }, [
  { role: 'assistant', content: 'Which chapter should I quiz you on?' },
], 'Chapter two');
assert.equal(clarification.answered, 0, 'does not count a setup clarification as a quiz answer');

const restored = learningProgressFromTurns([
  { role: 'user', content: 'Quiz me on this PDF' },
  { role: 'assistant', content: 'Question one: What does the first section explain?' },
  { role: 'user', content: 'It explains how cells use energy.' },
]);
assert.equal(restored.answered, 1, 'rebuilds study progress from saved chat turns');

console.log('Learning progress tests passed.');
