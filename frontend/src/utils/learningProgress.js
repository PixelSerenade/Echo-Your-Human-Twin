export const LEARNING_SET_SIZE = 5;

const START_PRACTICE = /\b(?:quiz me|test me|ask me (?:some |a few )?questions|practice questions|practise questions|flash ?cards|help me study|study with me|let's study|lets study)\b/i;
const ACCEPT_PRACTICE = /^\s*(?:yes|yeah|yep|sure|okay|ok|let's|lets|ready|go ahead)[.! ]*\s*$/i;
const QUIZ_INVITATION = /\b(?:ready to (?:dive into|start|try)|shall we (?:start|begin))\b[^?]*\b(?:quiz|question|word|list)\b/i;
const QUIZ_QUESTION = (message) => /\?/.test(message);
const CLARIFICATION_QUESTION = /\b(?:what topic|which topic|what subject|which subject|what chapter|which chapter|what part|which part|what level|how many questions|what would you like to study|ready to|would you like me to|do you want me to|tell me more)\b/i;

export function isLearningRequest(message = '') {
  return START_PRACTICE.test(message);
}

export function nextLearningProgress(previous, turns = [], question = '') {
  const lastAssistant = [...turns].reverse().find((turn) => turn.role === 'assistant')?.content || '';
  const acceptsInvitation = ACCEPT_PRACTICE.test(question) && QUIZ_INVITATION.test(lastAssistant);

  if (isLearningRequest(question) || acceptsInvitation) {
    return { active: true, answered: 0, target: LEARNING_SET_SIZE };
  }
  if (!previous?.active) return previous || null;

  const lastAssistantIsQuizPrompt = QUIZ_QUESTION(lastAssistant)
    && !CLARIFICATION_QUESTION.test(lastAssistant);
  if (!lastAssistantIsQuizPrompt || /^\s*(?:stop|pause|quit|end)(?:\s+(?:the )?(?:quiz|session|practice))?[.! ]*$/i.test(question)) {
    return previous;
  }

  const answered = Math.max(0, Number(previous.answered) || 0) + 1;
  const previousTarget = Math.max(LEARNING_SET_SIZE, Number(previous.target) || LEARNING_SET_SIZE);
  const target = answered > previousTarget ? previousTarget + LEARNING_SET_SIZE : previousTarget;
  return { ...previous, active: true, answered, target };
}

export function learningProgressFromTurns(turns = []) {
  let progress = null;
  const history = Array.isArray(turns) ? turns : [];
  for (let index = 0; index < history.length; index += 1) {
    const turn = history[index];
    if (turn.role !== 'user') continue;
    const context = history.slice(0, index);
    progress = nextLearningProgress(progress, context, turn.content || '');
  }
  return progress;
}
