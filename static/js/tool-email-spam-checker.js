// ── FAQ Accordion ──────────────────────────────────────
function toggleFaq(id) {
  const item = document.getElementById(id);
  const isOpen = item.classList.contains('open');
  document.querySelectorAll('.faq-item.open').forEach(i => i.classList.remove('open'));
  if (!isOpen) item.classList.add('open');
}

// ── Spam Dictionary & Weights ─────────────────────────
// A detailed dictionary of spam phrases with severity weights (1 = light, 3 = medium, 5 = severe)
const SPAM_RULES = [
  // Financial Scam / High Risk (Weight: 5)
  { phrase: "100% free", weight: 5 }, { phrase: "100% satisfied", weight: 5 }, { phrase: "billing", weight: 5 }, 
  { phrase: "buying judgments", weight: 5 }, { phrase: "cancel at any time", weight: 5 }, { phrase: "cash bonus", weight: 5 }, 
  { phrase: "cashcashcash", weight: 5 }, { phrase: "casino", weight: 5 }, { phrase: "cents on the dollar", weight: 5 }, 
  { phrase: "consolidate debt", weight: 5 }, { phrase: "credit card", weight: 5 }, { phrase: "credit offers", weight: 5 }, 
  { phrase: "cure", weight: 5 }, { phrase: "debt", weight: 5 }, { phrase: "eliminate bad credit", weight: 5 }, 
  { phrase: "earn extra cash", weight: 5 }, { phrase: "earn money", weight: 5 }, { phrase: "fast cash", weight: 5 }, 
  { phrase: "financial freedom", weight: 5 }, { phrase: "free investment", weight: 5 }, { phrase: "free money", weight: 5 }, 
  { phrase: "full refund", weight: 5 }, { phrase: "get out of debt", weight: 5 }, { phrase: "get paid", weight: 5 }, 
  { phrase: "hidden charges", weight: 5 }, { phrase: "human growth hormone", weight: 5 }, { phrase: "least math", weight: 5 }, 
  { phrase: "loans", weight: 5 }, { phrase: "make money", weight: 5 }, { phrase: "million dollars", weight: 5 }, 
  { phrase: "miracle", weight: 5 }, { phrase: "money back", weight: 5 }, { phrase: "money making", weight: 5 }, 
  { phrase: "mortgage", weight: 5 }, { phrase: "mortgage rates", weight: 5 }, { phrase: "multi-level marketing", weight: 5 }, 
  { phrase: "online pharmacy", weight: 5 }, { phrase: "passwords", weight: 5 }, { phrase: "pure profit", weight: 5 }, 
  { phrase: "refinance", weight: 5 }, { phrase: "refund", weight: 5 }, { phrase: "risk free", weight: 5 }, { phrase: "risk-free", weight: 5 }, 
  { phrase: "rolex", weight: 5 }, { phrase: "save big money", weight: 5 }, { phrase: "serious cash", weight: 5 }, 
  { phrase: "social security number", weight: 5 }, { phrase: "unsecured credit", weight: 5 }, { phrase: "unsecured debt", weight: 5 }, 
  { phrase: "valium", weight: 5 }, { phrase: "viagra", weight: 5 }, { phrase: "vicodin", weight: 5 }, { phrase: "weight loss", weight: 5 }, 
  { phrase: "winner", weight: 5 }, { phrase: "winning", weight: 5 }, { phrase: "won", weight: 5 }, { phrase: "work from home", weight: 5 }, 
  { phrase: "xanax", weight: 5 }, { phrase: "you are a winner", weight: 5 }, { phrase: "you have been selected", weight: 5 },
  
  // Aggressive Marketing / Urgency (Weight: 4)
  { phrase: "act now", weight: 4 }, { phrase: "action required", weight: 4 }, { phrase: "apply now", weight: 4 }, 
  { phrase: "compare rates", weight: 4 }, { phrase: "congratulations", weight: 4 }, { phrase: "do it today", weight: 4 }, 
  { phrase: "don't delete", weight: 4 }, { phrase: "exclusive deal", weight: 4 }, { phrase: "free access", weight: 4 }, 
  { phrase: "free bonus", weight: 4 }, { phrase: "free gift", weight: 4 }, { phrase: "get it now", weight: 4 }, 
  { phrase: "get started now", weight: 4 }, { phrase: "guarantee", weight: 4 }, { phrase: "guaranteed", weight: 4 }, 
  { phrase: "important information regarding", weight: 4 }, { phrase: "incredible deal", weight: 4 }, { phrase: "limited time", weight: 4 }, 
  { phrase: "lowest price", weight: 4 }, { phrase: "no cost", weight: 4 }, { phrase: "no credit check", weight: 4 }, 
  { phrase: "no fees", weight: 4 }, { phrase: "no gimmick", weight: 4 }, { phrase: "no hidden costs", weight: 4 }, 
  { phrase: "no hidden fees", weight: 4 }, { phrase: "no interest", weight: 4 }, { phrase: "no investment", weight: 4 }, 
  { phrase: "no obligation", weight: 4 }, { phrase: "no purchase necessary", weight: 4 }, { phrase: "no questions asked", weight: 4 }, 
  { phrase: "no strings attached", weight: 4 }, { phrase: "obligation", weight: 4 }, { phrase: "once in lifetime", weight: 4 }, 
  { phrase: "order now", weight: 4 }, { phrase: "print form signature", weight: 4 }, { phrase: "promise", weight: 4 }, 
  { phrase: "removal instructions", weight: 4 }, { phrase: "reserves the right", weight: 4 }, { phrase: "satisfaction guaranteed", weight: 4 }, 
  { phrase: "sign up free today", weight: 4 }, { phrase: "special promotion", weight: 4 }, { phrase: "stock alert", weight: 4 }, 
  { phrase: "subject to credit", weight: 4 }, { phrase: "supplies are limited", weight: 4 }, { phrase: "take action", weight: 4 }, 
  { phrase: "terms and conditions", weight: 4 }, { phrase: "the best rates", weight: 4 }, { phrase: "the following form", weight: 4 }, 
  { phrase: "this isn't a scam", weight: 4 }, { phrase: "this isn't junk", weight: 4 }, { phrase: "this isn't spam", weight: 4 }, 
  { phrase: "urgent", weight: 4 }, { phrase: "we hate spam", weight: 4 }, { phrase: "what are you waiting for", weight: 4 }, 
  { phrase: "while supplies last", weight: 4 }, { phrase: "who really wins", weight: 4 }, { phrase: "why pay more", weight: 4 },
  
  // Common Marketing Words (Weight: 2)
  { phrase: "50% off", weight: 2 }, { phrase: "affordable", weight: 2 }, { phrase: "all natural", weight: 2 }, 
  { phrase: "all new", weight: 2 }, { phrase: "as seen on", weight: 2 }, { phrase: "bargain", weight: 2 }, 
  { phrase: "be your own boss", weight: 2 }, { phrase: "best price", weight: 2 }, { phrase: "bonus", weight: 2 }, 
  { phrase: "boss", weight: 2 }, { phrase: "bulk email", weight: 2 }, { phrase: "buy", weight: 2 }, 
  { phrase: "buy direct", weight: 2 }, { phrase: "cash", weight: 2 }, { phrase: "cheap", weight: 2 }, 
  { phrase: "check", weight: 2 }, { phrase: "claims", weight: 2 }, { phrase: "clearance", weight: 2 }, 
  { phrase: "click below", weight: 2 }, { phrase: "click here", weight: 2 }, { phrase: "complimentary", weight: 2 }, 
  { phrase: "confidential", weight: 2 }, { phrase: "credit", weight: 2 }, { phrase: "dear friend", weight: 2 }, 
  { phrase: "direct email", weight: 2 }, { phrase: "direct marketing", weight: 2 }, { phrase: "discount", weight: 2 }, 
  { phrase: "drastically reduced", weight: 2 }, { phrase: "earn", weight: 2 }, { phrase: "expect to earn", weight: 2 }, 
  { phrase: "extra income", weight: 2 }, { phrase: "free", weight: 2 }, { phrase: "free consultation", weight: 2 }, 
  { phrase: "free hosting", weight: 2 }, { phrase: "free info", weight: 2 }, { phrase: "free membership", weight: 2 }, 
  { phrase: "free offer", weight: 2 }, { phrase: "free preview", weight: 2 }, { phrase: "free quote", weight: 2 }, 
  { phrase: "free trial", weight: 2 }, { phrase: "giveaway", weight: 2 }, { phrase: "great offer", weight: 2 }, 
  { phrase: "hidden", weight: 2 }, { phrase: "home based", weight: 2 }, { phrase: "income", weight: 2 }, 
  { phrase: "increase sales", weight: 2 }, { phrase: "increase traffic", weight: 2 }, { phrase: "investment", weight: 2 }, 
  { phrase: "join millions", weight: 2 }, { phrase: "leave", weight: 2 }, { phrase: "lifetime", weight: 2 }, 
  { phrase: "market research", weight: 2 }, { phrase: "marketing", weight: 2 }, { phrase: "mass email", weight: 2 }, 
  { phrase: "meet singles", weight: 2 }, { phrase: "money", weight: 2 }, { phrase: "month trial offer", weight: 2 }, 
  { phrase: "more internet traffic", weight: 2 }, { phrase: "name brand", weight: 2 }, { phrase: "new customers", weight: 2 }, 
  { phrase: "no catch", weight: 2 }, { phrase: "not intended", weight: 2 }, { phrase: "not spam", weight: 2 }, 
  { phrase: "offer", weight: 2 }, { phrase: "one time", weight: 2 }, { phrase: "online biz opportunity", weight: 2 }, 
  { phrase: "online degree", weight: 2 }, { phrase: "online marketing", weight: 2 }, { phrase: "opportunity", weight: 2 }, 
  { phrase: "opt in", weight: 2 }, { phrase: "pennies a day", weight: 2 }, { phrase: "performance", weight: 2 }, 
  { phrase: "pre-approved", weight: 2 }, { phrase: "price", weight: 2 }, { phrase: "prize", weight: 2 }, 
  { phrase: "prizes", weight: 2 }, { phrase: "problem", weight: 2 }, { phrase: "profit", weight: 2 }, 
  { phrase: "purchase", weight: 2 }, { phrase: "quote", weight: 2 }, { phrase: "rates", weight: 2 }, 
  { phrase: "remove", weight: 2 }, { phrase: "reverses", weight: 2 }, { phrase: "sales", weight: 2 }, 
  { phrase: "satisfaction", weight: 2 }, { phrase: "save up to", weight: 2 }, { phrase: "score", weight: 2 }, 
  { phrase: "search engine", weight: 2 }, { phrase: "secret", weight: 2 }, { phrase: "seo", weight: 2 }, 
  { phrase: "shoe", weight: 2 }, { phrase: "shopping spree", weight: 2 }, { phrase: "spam", weight: 2 }, 
  { phrase: "stop", weight: 2 }, { phrase: "success", weight: 2 }, { phrase: "thousands", weight: 2 }, 
  { phrase: "traffic", weight: 2 }, { phrase: "trial", weight: 2 }, { phrase: "unlimited", weight: 2 }, 
  { phrase: "web traffic", weight: 2 }, { phrase: "win", weight: 2 }, { phrase: "your income", weight: 2 }
];

// 1. Precompile regex once for all rules mapping -> performance boost
const COMPILED_RULES = SPAM_RULES.map(rule => ({
  ...rule,
  regex: new RegExp(`\\b${rule.phrase.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}\\b`, 'gi')
}));


// ── Logic Layer (Separated for Scalability) ────────────

function getCapsScore(text) {
  const words = text.split(/\s+/);
  const capsWords = words.filter(w => w === w.toUpperCase() && w.length > 3 && /[A-Z]/.test(w));
  return {
    score: capsWords.length > 2 ? capsWords.length * 2 : 0, // Light penality for caps
    matches: capsWords.length > 2 ? ["excessive ALL CAPS"] : []
  };
}

function getLinkScore(text) {
  const links = text.match(/https?:\/\/[^\s]+/gi) || [];
  return {
    score: links.length > 2 ? (links.length - 2) * 5 : 0, // Heavy penality if > 2 links
    matches: links.length > 2 ? ["too many links (>2)"] : []
  };
}

function getPunctuationScore(text) {
  const excl_matches = text.match(/!{2,}/g) || [];
  const dollar_matches = text.match(/\${2,}/g) || [];
  
  let score = 0;
  let matches = [];
  
  if (excl_matches.length > 0) {
    score += excl_matches.length * 3;
    matches.push("excessive punctuation (!!!)");
  }
  
  if (dollar_matches.length > 0) {
    score += dollar_matches.length * 5;
    matches.push("excessive symbols ($$$)");
  }
  
  return { score, matches };
}

function getSpamScore(text) {
  let score = 0;
  let matches = []; // Now stores objects to hold frequencies

  for (const rule of COMPILED_RULES) {
    const rawMatches = text.match(rule.regex) || [];
    const occurrences = rawMatches.length;
    
    if (occurrences > 0) {
      score += rule.weight * 2 * Math.min(occurrences, 3); // Frequency sensitivity capped at 3
      matches.push({ phrase: rule.phrase, count: occurrences });
    }
  }

  return { score, matches };
}

function getSuggestions(matches) {
  const tips = [];
  const matchedPhrases = matches.map(m => m.phrase || m);
  
  if (matchedPhrases.includes("free") || matchedPhrases.includes("100% free")) {
    tips.push("Avoid using 'free' excessively; offer specific value instead.");
  }
  
  if (matchedPhrases.some(m => m.includes("act now") || m.includes("urgent") || m.includes("limited time"))) {
    tips.push("Reduce high-urgency phrases; they mimic common scam patterns.");
  }
  
  if (matchedPhrases.includes("too many links (>2)")) {
    tips.push("Keep cold emails to a maximum of 1 or 2 links max.");
  }
  
  if (matchedPhrases.some(m => m.includes("excessive"))) {
    tips.push("Avoid shouting at your reader; remove multiple exclamation marks and ALL CAPS.");
  }
  
  if (tips.length === 0 && matches.length > 0) {
    tips.push("Consider completely rephrasing the flagged spam words.");
  } else if (tips.length === 0) {
    tips.push("Keep your email under 125 words for higher reply rates.");
    tips.push("Personalize the subject line to prevent algorithmic filtering.");
  }
  
  return tips;
}

function analyzeEmail(subject, body, espType = 'general') {
  const fullText = subject + "\n" + body;
  
  // 1. Word Count & Reading Time
  const words = fullText.trim().match(/\S+/g) || [];
  const wordCount = words.length;
  const readingTimeSeconds = Math.ceil(wordCount / 4);
  
  if (wordCount === 0) {
    return { wordCount: 0, readingTimeSeconds: 0, score: 100, classification: 'empty', uniqueMatches: [], tips: [], breakdown: null };
  }

  // 2. Score Evaluations
  const spamData = getSpamScore(fullText);
  const capsData = getCapsScore(fullText);
  const linkData = getLinkScore(fullText);
  const puncData = getPunctuationScore(fullText);
  
  const rawMatches = [...spamData.matches, ...capsData.matches.map(m => ({phrase: m, count: 1})), ...linkData.matches.map(m => ({phrase: m, count: 1})), ...puncData.matches.map(m => ({phrase: m, count: 1}))];
  
  // Deduplicate matches but keep occurrence count
  const uniqueMatchesMap = new Map();
  rawMatches.forEach(m => {
    if (uniqueMatchesMap.has(m.phrase)) {
      uniqueMatchesMap.get(m.phrase).count = Math.max(uniqueMatchesMap.get(m.phrase).count, m.count);
    } else {
      uniqueMatchesMap.set(m.phrase, { phrase: m.phrase, count: m.count });
    }
  });
  const uniqueMatches = Array.from(uniqueMatchesMap.values());

  // Positive Behaviors
  const GOOD_PATTERNS = [
    /quick question/gi,
    /not sure if relevant/gi,
    /thought this might help/gi,
    /open to a quick chat/gi
  ];
  let positiveScore = 0;
  GOOD_PATTERNS.forEach(p => {
    if (p.test(fullText)) positiveScore += 3;
  });

  // 3. Score Normalization
  let score = 100;
  
  // Density-Based Scoring
  const spamDensity = uniqueMatches.length / Math.max(1, wordCount);
  const densityPenalty = Math.floor(spamDensity * 150);

  let totalDeductions = spamData.score + capsData.score + linkData.score + puncData.score + densityPenalty;

  // ESP Specific Adjustments
  let espPenalty = 0;
  if (espType === 'gmail') {
      // Gmail is extremely sensitive to links and multiple images (images not tracked here but links are)
      if (linkData.score > 0) espPenalty += 10;
      // Gmail is sensitive to promotional keywords in subject lines
      const promoWords = /\b(free|offer|discount|save|percent|%)\b/i;
      if (promoWords.test(subject)) espPenalty += 5;
  } else if (espType === 'outlook') {
      // Outlook Enterprise is very strict on aggressive capitalization and punctuation
      if (capsData.score > 0) espPenalty += 10;
      if (puncData.score > 0) espPenalty += 10;
  }
  
  totalDeductions += espPenalty;

  score -= totalDeductions;
  score += positiveScore;

  // Base structural penalties
  let lengthPenalty = 0;
  if (wordCount > 150) lengthPenalty = Math.floor((wordCount - 150) * 0.1); 
  if (wordCount < 10) lengthPenalty += 20;

  score -= lengthPenalty;

  // Normalize to 0-100 range
  score = Math.min(100, Math.max(0, score));

  // 4. Classification
  let classification = 'good';
  if (score >= 85) classification = 'good';
  else if (score >= 65) classification = 'risk';
  else if (score >= 40) classification = 'high-risk';
  else classification = 'spam';

  const tips = getSuggestions(uniqueMatches);

  return {
    wordCount,
    readingTimeSeconds,
    score,
    classification,
    uniqueMatches,
    tips,
    breakdown: {
      spam: spamData.score,
      caps: capsData.score,
      links: linkData.score,
      punctuation: puncData.score,
      density: densityPenalty,
      positive: positiveScore,
      length: lengthPenalty,
      esp: espPenalty
    }
  };
}


// ── Interface (UI bindings) ───────────────────────────

const subjectInput = document.getElementById('subjectInput');
const bodyInput = document.getElementById('bodyInput');

const wordCountEl = document.getElementById('wordCount');
const readingTimeEl = document.getElementById('readingTime');
const spamCountEl = document.getElementById('spamCount');
const spamWordsContainer = document.getElementById('spamWordsContainer');
const spamChips = document.getElementById('spamChips');
const scoreText = document.getElementById('scoreText');
const scorePath = document.getElementById('scorePath');
const scoreStatus = document.getElementById('scoreStatus');
const scoreDescription = document.getElementById('scoreDescription');

const tipsList = document.getElementById('tipsList');
const breakdownContainer = document.getElementById('breakdownContainer');
const breakdownItems = document.getElementById('breakdownItems');
const espSelect = document.getElementById('espSelect'); // Might not exist yet in DOM but good to have

const checkBtn = document.getElementById('checkBtn');
const clearBtn = document.getElementById('clearBtn');
const pasteExampleBtn = document.getElementById('pasteExampleBtn');

const EXAMPLE_TEXT = `Subject: URGENT: Increase sales with 100% free software

Hi John,

I wanted to quickly reach out because you have been selected to try our all new marketing platform. We guarantee it will increase traffic and bring you new customers immediately.

It's completely risk-free and requires no credit card. We hate spam, so there's no hidden fees and no catch. Act now because this is a limited time offer and supplies are limited.

Click here to claim your free trial and make money today! https://example.com/claim https://example.com/more https://example.com/one-more

Don't miss out,
Sarah`;

function renderUI() {
  const subject = subjectInput.value;
  const body = bodyInput.value;
  const espType = espSelect ? espSelect.value : 'general';
  
  // Run logic
  const result = analyzeEmail(subject, body, espType);
  
  // Render Stats
  wordCountEl.textContent = result.wordCount;
  readingTimeEl.textContent = result.readingTimeSeconds < 60 ? `${result.readingTimeSeconds}s` : `${Math.floor(result.readingTimeSeconds/60)}m ${result.readingTimeSeconds%60}s`;
  spamCountEl.textContent = result.uniqueMatches.length;
  
  const statBox = spamCountEl.parentElement;
  
  // Render Spam Chips
  if (result.uniqueMatches.length > 0) {
    spamWordsContainer.style.display = 'block';
    statBox.classList.add('highlight-spam');
    statBox.classList.remove('safe');
    statBox.classList.toggle('danger', result.classification === 'spam');

    spamChips.innerHTML = result.uniqueMatches.map(m => `
      <div class="spam-chip" data-phrase="${m.phrase}" onclick="highlightPhrase('${m.phrase}')" style="cursor: pointer;" title="Found ${m.count} time(s). Click to highlight.">
        <span>!</span> ${m.phrase} <small style="opacity:0.7">(${m.count})</small>
      </div>
    `).join('');
  } else {
    spamWordsContainer.style.display = 'none';
    statBox.classList.remove('highlight-spam', 'danger');
    statBox.classList.toggle('safe', result.wordCount > 0);
    spamChips.innerHTML = '';
  }

  // Render Breakdown (Explainability)
  if (result.breakdown && Object.values(result.breakdown).some(v => v > 0)) {
    if (breakdownContainer) breakdownContainer.style.display = 'block';
    if (breakdownItems) {
      let breakdownHtml = '';
      if (result.breakdown.spam > 0) breakdownHtml += `<li><span>Spam Words</span><span class="breakdown-value bad">-${result.breakdown.spam}</span></li>`;
      if (result.breakdown.caps > 0) breakdownHtml += `<li><span>Excessive CAPS</span><span class="breakdown-value bad">-${result.breakdown.caps}</span></li>`;
      if (result.breakdown.links > 0) breakdownHtml += `<li><span>Too Many Links</span><span class="breakdown-value bad">-${result.breakdown.links}</span></li>`;
      if (result.breakdown.punctuation > 0) breakdownHtml += `<li><span>Aggressive Punctuation</span><span class="breakdown-value bad">-${result.breakdown.punctuation}</span></li>`;
      if (result.breakdown.density > 0) breakdownHtml += `<li><span>High Spam Density</span><span class="breakdown-value bad">-${result.breakdown.density}</span></li>`;
      if (result.breakdown.length > 0) breakdownHtml += `<li><span>Suboptimal Length</span><span class="breakdown-value bad">-${result.breakdown.length}</span></li>`;
      if (result.breakdown.esp > 0) breakdownHtml += `<li><span>ESP Strict Filtering</span><span class="breakdown-value bad">-${result.breakdown.esp}</span></li>`;
      if (result.breakdown.positive > 0) breakdownHtml += `<li><span>Great Phrasing</span><span class="breakdown-value good">+${result.breakdown.positive}</span></li>`;
      breakdownItems.innerHTML = breakdownHtml;
    }
  } else {
    if (breakdownContainer) breakdownContainer.style.display = 'none';
  }

  // Render Tips
  if (result.tips.length > 0) {
    tipsList.innerHTML = result.tips.map(t => `<li>${t}</li>`).join('');
  } else {
    tipsList.innerHTML = '<li>You are all set!</li>';
  }

  // Render Score Circle
  if (result.classification === 'empty') {
    setCircle(100, '#9ca3af', 'Enter Text', 'Paste an email to analyze it.');
    return;
  }

  let color, label, desc;
  if (result.classification === 'good') {
    color = '#10b981'; // Green
    label = 'Looks Good!';
    desc = 'Low risk of triggering spam filters. Good job.';
  } else if (result.classification === 'risk') {
    color = '#f59e0b'; // Yellow/Orange
    label = 'Borderline';
    desc = 'Several spam triggers detected. Consider rewriting.';
  } else if (result.classification === 'high-risk') {
    color = '#f97316'; // Orange
    label = 'High Risk';
    desc = 'Heavy use of spam triggers. High chance of promotion folder.';
  } else {
    color = '#ef4444'; // Red
    label = 'Spam Trapped';
    desc = 'Almost certainly going to the spam folder.';
  }

  setCircle(result.score, color, label, desc);
}

function setCircle(score, color, label, desc) {
  scorePath.setAttribute('stroke-dasharray', `${score}, 100`);
  scorePath.style.stroke = color;
  scoreText.textContent = score;
  
  scoreStatus.textContent = label;
  scoreStatus.style.color = color;
  scoreDescription.textContent = desc;

  const dot = document.querySelector('.panel-title .spam-dot');
  if (dot) dot.style.background = color;
}

// ── Highlighting System ───────────────────────────────

function highlightPhrase(phrase) {
  if (!phrase) return;
  // Clear any existing custom highlights from our textarea 
  // Native textareas don't support rich HTML highlighting. 
  // We'll simulate it by temporarily selecting the text natively in the body textarea.
  const bodyText = bodyInput.value.toLowerCase();
  const searchPhrase = phrase.toLowerCase();
  
  const startIndex = bodyText.indexOf(searchPhrase);
  
  if (startIndex !== -1) {
    bodyInput.focus();
    bodyInput.setSelectionRange(startIndex, startIndex + phrase.length);
  } else {
    const subjectText = subjectInput.value.toLowerCase();
    const subjectIndex = subjectText.indexOf(searchPhrase);
    if(subjectIndex !== -1) {
      subjectInput.focus();
      subjectInput.setSelectionRange(subjectIndex, subjectIndex + phrase.length);
    }
  }
}

// ── Bindings ──────────────────────────────────────────

// 5. Input Debouncing
function debounce(fn, delay = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

const debouncedRender = debounce(renderUI, 300);

subjectInput.addEventListener('input', debouncedRender);
bodyInput.addEventListener('input', debouncedRender);
if (espSelect) espSelect.addEventListener('change', renderUI);

checkBtn.addEventListener('click', () => {
  const btnIcon = checkBtn.querySelector('i');
  btnIcon.setAttribute('data-lucide', 'loader-2');
  btnIcon.classList.add('lucide-spin');
  if (window.lucide) lucide.createIcons();
  
  // Simulate load
  setTimeout(() => {
    renderUI();
    btnIcon.setAttribute('data-lucide', 'search');
    btnIcon.classList.remove('lucide-spin');
    if (window.lucide) lucide.createIcons();
  }, 400);
});

clearBtn.addEventListener('click', () => {
  subjectInput.value = '';
  bodyInput.value = '';
  renderUI();
});

pasteExampleBtn.addEventListener('click', () => {
  subjectInput.value = '';
  bodyInput.value = EXAMPLE_TEXT;
  renderUI();
});

// ── Init ──────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
  setCircle(100, '#9ca3af', 'Waiting...', 'Paste an email to see your deliverability score.');
  
  const style = document.createElement('style');
  style.textContent = `
    @keyframes spin { 100% { transform: rotate(360deg); } }
    .lucide-spin { animation: spin 1s linear infinite; }
  `;
  document.head.appendChild(style);
});
