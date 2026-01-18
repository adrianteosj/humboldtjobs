/**
 * Netlify Function: AI Chat for Humboldt Jobs
 * Uses Google Gemini API (free tier) with Bigfoot persona
 */

const { GoogleGenerativeAI } = require('@google/generative-ai');

// In-memory cache for responses (persists across warm function instances)
const responseCache = new Map();
const CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours
const MAX_CACHE_SIZE = 100;

// Content moderation - blocked patterns
const BLOCKED_PATTERNS = [
    // Profanity (common variations)
    /\b(f+u+c+k+|sh+[i1]+t+|bull+sh+[i1]+t+|a+ss+h+o+l+e*|damn+|b+[i1]+t+c+h+|bastard|crap+)\b/i,
    // Slurs (partial patterns)
    /\b(n+[i1]+g+|f+a+g+|ret+ard|tr+ann+y)\b/i,
    // Sexual content
    /\b(sex+y*|p+o+r+n+|nude|xxx|horny|b+o+o+b+|d+[i1]+c+k+|p+u+s+s+y+|c+o+c+k+)\b/i,
    // Violence
    /\b(k+[i1]+l+l+\s+(you|me|them)|murder|shoot|stab)\b/i,
    // Drugs (non-medical context)
    /\b(weed|cocaine|meth|heroin|drugs)\b/i,
];

/**
 * Check if content contains inappropriate language
 */
function containsInappropriateContent(text) {
    const normalized = text.toLowerCase();
    return BLOCKED_PATTERNS.some(pattern => pattern.test(normalized));
}

/**
 * Get moderated response for inappropriate content
 */
function getModeratedResponse() {
    const responses = [
        "Whoa there! I'm just here to help with jobs - even Bigfoot has boundaries. 👣 What type of work are you interested in?",
        "Let's keep this about careers, friend. I've been hiding in these woods to help people find jobs, not for... that. What field interests you?",
        "I'm going to pretend I didn't see that. 👀 Let's talk jobs instead - what kind of work are you looking for?"
    ];
    return responses[Math.floor(Math.random() * responses.length)];
}

// Jobs data (loaded once per function instance)
let jobsData = null;

/**
 * Load jobs data from the static JSON file
 */
async function loadJobsData() {
    if (jobsData) return jobsData;
    
    // URLs to try in order (local dev first, then production)
    const urls = [
        'http://localhost:8888/static/jobs.json',  // Local dev
        'https://jobsinhumboldt.com/static/jobs.json'  // Production
    ];
    
    for (const url of urls) {
        try {
            const response = await fetch(url, { timeout: 5000 });
            if (response.ok) {
                jobsData = await response.json();
                console.log(`Loaded ${jobsData.length} jobs from ${url}`);
                return jobsData;
            }
        } catch (error) {
            console.log(`Failed to fetch from ${url}: ${error.message}`);
        }
    }
    
    // Fallback: return empty array
    console.error('Failed to load jobs data from any source');
    return [];
}

/**
 * Generate slug from employer name for Humboldt Jobs URL
 */
function generateSlug(name) {
    return name.toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-')
        .trim();
}

/**
 * Normalize query for cache lookup
 */
function normalizeQuery(query) {
    return query.toLowerCase().trim().replace(/\s+/g, ' ').slice(0, 100);
}

/**
 * Check cache for a response
 */
function getCachedResponse(query) {
    const key = normalizeQuery(query);
    const cached = responseCache.get(key);
    
    if (cached && (Date.now() - cached.timestamp) < CACHE_TTL) {
        cached.hits++;
        return cached.response;
    }
    
    return null;
}

/**
 * Store response in cache
 */
function cacheResponse(query, response) {
    const key = normalizeQuery(query);
    
    // Evict oldest if at capacity
    if (responseCache.size >= MAX_CACHE_SIZE) {
        const oldest = [...responseCache.entries()]
            .sort((a, b) => a[1].timestamp - b[1].timestamp)[0];
        if (oldest) {
            responseCache.delete(oldest[0]);
        }
    }
    
    responseCache.set(key, {
        response,
        timestamp: Date.now(),
        hits: 1
    });
}

/**
 * Extract keywords from user query
 */
function extractKeywords(query) {
    const stopWords = new Set([
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
        'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
        'because', 'until', 'while', 'although', 'though', 'after', 'before',
        'any', 'job', 'jobs', 'work', 'position', 'positions', 'opening', 'openings',
        'available', 'hiring', 'looking', 'find', 'search', 'humboldt', 'county',
        'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am',
        'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'him', 'his', 'she',
        'her', 'it', 'its', 'they', 'them', 'their'
    ]);
    
    return query.toLowerCase()
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/)
        .filter(word => word.length > 2 && !stopWords.has(word));
}

/**
 * Known job categories for filtering
 */
const CATEGORY_KEYWORDS = {
    'healthcare': ['healthcare', 'health', 'medical', 'nursing', 'nurse', 'hospital', 'clinical'],
    'education': ['education', 'teacher', 'teaching', 'school', 'instructor', 'professor'],
    'government': ['government', 'city', 'county', 'public', 'municipal'],
    'retail': ['retail', 'store', 'sales', 'cashier'],
    'hospitality': ['hospitality', 'hotel', 'restaurant', 'food service'],
    'construction': ['construction', 'engineering', 'building'],
    'nonprofit': ['nonprofit', 'non-profit', 'social services']
};

/**
 * Experience level mapping for query detection
 */
const EXPERIENCE_KEYWORDS = {
    'entry': ['entry', 'entry-level', 'starting', 'beginner', 'no experience', 'just starting', 'new grad', 'fresh'],
    'mid': ['mid-level', 'experienced', 'some experience', '2-5 years', '3 years', 'intermediate'],
    'senior': ['senior', 'lead', 'manager', 'director', '5+ years', 'experienced', 'advanced', 'expert']
};

/**
 * Job type mapping for query detection
 */
const JOB_TYPE_KEYWORDS = {
    'full-time': ['full-time', 'full time', 'fulltime', 'ft'],
    'part-time': ['part-time', 'part time', 'parttime', 'pt', 'flexible'],
    'per diem': ['per diem', 'as needed', 'on call'],
    'temporary': ['temporary', 'temp', 'seasonal', 'contract']
};

/**
 * Detect if query mentions a specific category
 */
function detectCategory(query) {
    const queryLower = query.toLowerCase();
    for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
        for (const keyword of keywords) {
            if (queryLower.includes(keyword)) {
                return category;
            }
        }
    }
    return null;
}

/**
 * Detect experience level from query
 */
function detectExperienceLevel(query) {
    const queryLower = query.toLowerCase();
    for (const [level, keywords] of Object.entries(EXPERIENCE_KEYWORDS)) {
        for (const keyword of keywords) {
            if (queryLower.includes(keyword)) {
                return level.charAt(0).toUpperCase() + level.slice(1); // Entry, Mid, Senior
            }
        }
    }
    return null;
}

/**
 * Detect job type from query
 */
function detectJobType(query) {
    const queryLower = query.toLowerCase();
    for (const [type, keywords] of Object.entries(JOB_TYPE_KEYWORDS)) {
        for (const keyword of keywords) {
            if (queryLower.includes(keyword)) {
                return type;
            }
        }
    }
    return null;
}

/**
 * Detect salary range from query
 */
function detectSalaryRange(query) {
    const queryLower = query.toLowerCase();
    
    // Check for specific salary mentions
    const salaryMatch = query.match(/\$\s*(\d{1,3}(?:,\d{3})*|\d+)(?:k)?/i);
    if (salaryMatch) {
        let amount = parseFloat(salaryMatch[1].replace(/,/g, ''));
        // If it looks like shorthand (e.g., $50k), multiply by 1000
        if (queryLower.includes('k') || amount < 200) {
            amount *= 1000;
        }
        return { min: amount * 0.8, max: amount * 1.2 }; // +/- 20% range
    }
    
    // Check for salary descriptors
    if (queryLower.includes('high pay') || queryLower.includes('good pay') || queryLower.includes('well pay')) {
        return { min: 60000, max: null };
    }
    
    return null;
}

/**
 * Score job relevance to query using enriched job data
 */
function scoreJob(job, keywords, filters = {}) {
    let score = 0;
    const titleLower = (job.title || '').toLowerCase();
    const employerLower = (job.employer || '').toLowerCase();
    const categoryLower = (job.category || '').toLowerCase();
    const locationLower = (job.location || '').toLowerCase();
    const descriptionLower = (job.description || '').toLowerCase();
    const requirementsLower = (job.requirements || '').toLowerCase();
    const jobTypeLower = (job.job_type || '').toLowerCase();
    const expLevelLower = (job.experience_level || '').toLowerCase();
    
    // Category match - very important
    if (filters.category && categoryLower.includes(filters.category)) {
        score += 100;
    }
    
    // Experience level match - high importance
    if (filters.experienceLevel) {
        if (expLevelLower.includes(filters.experienceLevel.toLowerCase())) {
            score += 50;
        } else if (job.experience_level) {
            // Penalize mismatched experience levels
            score -= 10;
        }
    }
    
    // Job type match - high importance
    if (filters.jobType) {
        if (jobTypeLower.includes(filters.jobType.toLowerCase())) {
            score += 50;
        } else if (job.job_type) {
            // Don't penalize if no specific type requested
        }
    }
    
    // Salary range match
    if (filters.salaryRange && job.salary_max) {
        if (filters.salaryRange.min && job.salary_max >= filters.salaryRange.min) {
            score += 30;
        }
        if (filters.salaryRange.max && job.salary_min && job.salary_min <= filters.salaryRange.max) {
            score += 20;
        }
    }
    
    // Keyword matching
    for (const keyword of keywords) {
        const skipWords = ['full', 'time', 'part', 'entry', 'level', 'starting'];
        if (skipWords.includes(keyword)) continue;
        
        // Title matches are most valuable
        if (titleLower.includes(keyword)) {
            score += 15;
        }
        // Category matches (if not already boosted)
        if (!filters.category && categoryLower.includes(keyword)) {
            score += 20;
        }
        // Description matches
        if (descriptionLower.includes(keyword)) {
            score += 5;
        }
        // Requirements matches
        if (requirementsLower.includes(keyword)) {
            score += 5;
        }
        // Employer matches
        if (employerLower.includes(keyword)) score += 8;
        // Location matches
        if (locationLower.includes(keyword)) score += 5;
    }
    
    // Boost jobs with rich data (better user experience)
    if (job.salary && job.salary.trim()) score += 3;
    if (job.salary_min) score += 2; // Parsed salary available
    if (job.description) score += 2;
    if (job.requirements) score += 1;
    if (job.benefits) score += 1;
    
    // Prefer recent jobs
    if (job.posted_date) {
        const postedDate = new Date(job.posted_date);
        const daysSincePosted = (Date.now() - postedDate.getTime()) / (1000 * 60 * 60 * 24);
        if (daysSincePosted < 7) score += 5; // Within a week
        else if (daysSincePosted < 30) score += 2; // Within a month
    }
    
    return score;
}

/**
 * Find relevant jobs for the query using enriched data
 * @param {Array} jobs - All available jobs
 * @param {string} query - The search query
 * @param {number} limit - Max jobs to return
 * @param {Array} excludeTitles - Job titles to exclude (already shown)
 */
function findRelevantJobs(jobs, query, limit = 10, excludeTitles = []) {
    const keywords = extractKeywords(query);
    const queryLower = query.toLowerCase();
    
    // Filter out already-shown jobs
    let availableJobs = jobs;
    if (excludeTitles.length > 0) {
        const excludeSet = new Set(excludeTitles.map(t => t.toLowerCase().trim()));
        availableJobs = jobs.filter(job => 
            !excludeSet.has((job.title || '').toLowerCase().trim())
        );
    }
    
    // Detect all filters from query
    const filters = {
        category: detectCategory(query),
        experienceLevel: detectExperienceLevel(query),
        jobType: detectJobType(query),
        salaryRange: detectSalaryRange(query)
    };
    
    // Highest paying query - use parsed salary_max for accurate sorting
    if (queryLower.includes('highest pay') || queryLower.includes('best pay') || 
        queryLower.includes('most pay') || queryLower.includes('top pay') ||
        queryLower.includes('highest salary') || queryLower.includes('best salary')) {
        
        // Prefer jobs with parsed salary data
        let filteredJobs = availableJobs.filter(job => job.salary_max || (job.salary && job.salary.trim()));
        
        // Also filter by category if specified
        if (filters.category) {
            filteredJobs = filteredJobs.filter(job => 
                (job.category || '').toLowerCase().includes(filters.category)
            );
        }
        
        // Also filter by experience level if specified
        if (filters.experienceLevel) {
            const expFiltered = filteredJobs.filter(job => 
                (job.experience_level || '').toLowerCase().includes(filters.experienceLevel.toLowerCase())
            );
            if (expFiltered.length >= limit) {
                filteredJobs = expFiltered;
            }
        }
        
        return filteredJobs
            .sort((a, b) => {
                // Use parsed salary_max if available, fall back to extracting from text
                const aMax = a.salary_max || extractMaxSalary(a.salary);
                const bMax = b.salary_max || extractMaxSalary(b.salary);
                return bMax - aMax;
            })
            .slice(0, limit);
    }
    
    // Apply pre-filters to reduce pool
    let jobPool = availableJobs;
    
    // Category filter
    if (filters.category) {
        const categoryJobs = availableJobs.filter(job => 
            (job.category || '').toLowerCase().includes(filters.category)
        );
        if (categoryJobs.length >= limit) {
            jobPool = categoryJobs;
        }
    }
    
    // Job type filter (if specified)
    if (filters.jobType) {
        const typeJobs = jobPool.filter(job => 
            (job.job_type || '').toLowerCase().includes(filters.jobType)
        );
        if (typeJobs.length >= Math.min(limit, 3)) {
            jobPool = typeJobs;
        }
    }
    
    // Experience level filter (if specified)
    if (filters.experienceLevel) {
        const expJobs = jobPool.filter(job => 
            (job.experience_level || '').toLowerCase().includes(filters.experienceLevel.toLowerCase())
        );
        if (expJobs.length >= Math.min(limit, 3)) {
            jobPool = expJobs;
        }
    }
    
    // If no meaningful keywords, return from filtered pool
    if (keywords.length === 0) {
        return jobPool.slice(0, limit);
    }
    
    // Score and sort jobs using enriched scoring
    const scored = jobPool.map(job => ({
        job,
        score: scoreJob(job, keywords, filters)
    }));
    
    return scored
        .filter(item => item.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, limit)
        .map(item => item.job);
}

/**
 * Extract maximum salary value from salary string
 */
function extractMaxSalary(salaryStr) {
    if (!salaryStr) return 0;
    
    // Find all numbers in the salary string
    const numbers = salaryStr.match(/[\d,]+\.?\d*/g);
    if (!numbers) return 0;
    
    // Convert to numbers and find max
    const values = numbers.map(n => parseFloat(n.replace(/,/g, '')));
    let maxVal = Math.max(...values);
    
    // Normalize to annual if hourly
    if (salaryStr.toLowerCase().includes('hour') || salaryStr.toLowerCase().includes('/hr')) {
        maxVal = maxVal * 2080; // 40 hrs/week * 52 weeks
    } else if (salaryStr.toLowerCase().includes('month') || salaryStr.toLowerCase().includes('/mo')) {
        maxVal = maxVal * 12;
    }
    
    return maxVal;
}

/**
 * Build enriched context for the AI with all available job details
 */
function buildContext(jobs, totalJobs) {
    if (jobs.length === 0) {
        return `No specific jobs matched the query. Total jobs available: ${totalJobs}`;
    }
    
    let context = `Relevant jobs in Humboldt County (${jobs.length} matches):\n\n`;
    
    jobs.forEach((job, i) => {
        context += `${i + 1}. ${job.title}`;
        context += `\n   Employer: ${job.employer}`;
        context += `\n   Category: ${job.category}`;
        if (job.classification) context += ` (${job.classification})`;
        if (job.location) context += `\n   Location: ${job.location}`;
        
        // Salary info (use parsed values for more accurate info)
        if (job.salary_min && job.salary_max) {
            const type = job.salary_type === 'hourly' ? '/hr' : '/yr';
            if (job.salary_min === job.salary_max) {
                context += `\n   Salary: $${job.salary_min.toLocaleString()}${type}`;
            } else {
                context += `\n   Salary: $${job.salary_min.toLocaleString()} - $${job.salary_max.toLocaleString()}${type}`;
            }
        } else if (job.salary && job.salary.trim()) {
            context += `\n   Salary: ${job.salary}`;
        }
        
        // Job type and experience level
        if (job.job_type) context += `\n   Type: ${job.job_type}`;
        if (job.experience_level) context += `\n   Level: ${job.experience_level}`;
        if (job.education_required) context += `\n   Education: ${job.education_required}`;
        if (job.department) context += `\n   Department: ${job.department}`;
        if (job.is_remote) context += `\n   Remote: Yes`;
        
        // Description snippet (truncated for context)
        if (job.description) {
            const descSnippet = job.description.substring(0, 200);
            context += `\n   Description: ${descSnippet}...`;
        }
        
        // Requirements snippet
        if (job.requirements) {
            const reqSnippet = job.requirements.substring(0, 150);
            context += `\n   Requirements: ${reqSnippet}...`;
        }
        
        // Benefits mention
        if (job.benefits) {
            context += `\n   Benefits: Yes (details available)`;
        }
        
        // Posted date
        if (job.posted_date) {
            context += `\n   Posted: ${job.posted_date.split('T')[0]}`;
        }
        
        context += `\n   URL: ${job.url}`;
        context += '\n\n';
    });
    
    context += `Total jobs available on the site: ${totalJobs}`;
    
    return context;
}

/**
 * Generate AI response using Gemini with Bigfoot Career Advisor persona
 */
async function generateResponse(query, context, apiKey, relevantJobs, conversationHistory = []) {
    const genAI = new GoogleGenerativeAI(apiKey);
    const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash-lite' });
    
    const systemPrompt = `You are BIGFOOT - the legendary creature - working as a career advisor for Humboldt County job seekers.

PERSONALITY:
- Warm, helpful, slightly mysterious
- You've lived in Humboldt's redwoods for centuries
- Include ONE small Bigfoot reference per response (hiding, elusive, big feet, forest)
- Be helpful first, funny second

BIGFOOT REFERENCES (vary these):
- Good jobs here are hard to find... kinda like me.
- I've been hiding in these woods long enough to know where opportunities are.
- Unlike me, these jobs actually want to be found.
- Full-time? I get it - hiding in the forest doesn't pay the bills.
- Trees are great listeners but terrible at career advice.

PROFILING - You MUST gather this info BEFORE showing jobs:
Ask ONE question at a time in this order:

1. FIELD: What type of work interests you?
2. EXPERIENCE: Just starting out or experienced?
3. SCHEDULE: Full-time or part-time?

CRITICAL RULES:
- Do NOT add [SHOW_JOBS] until you know FIELD + EXPERIENCE + SCHEDULE
- When user has answered all 3 (FIELD, EXPERIENCE, SCHEDULE), you MUST start your response with [SHOW_JOBS]
- Ask ONE question, then STOP and wait
- Keep responses to 2-3 sentences max
- NEVER wrap your response in quotation marks
- ALWAYS end with [OPTIONS: ...] to give the user quick reply choices
- NEVER list jobs in your text response - job cards are shown separately by the UI
- Do NOT include job titles, employers, salaries, or job details in your text

RESPONSE FORMAT - ALWAYS include OPTIONS:
Your response here. Your question here?
[OPTIONS: Choice1 | Choice2 | Choice3]

PROFILING EXAMPLES WITH OPTIONS:

Asking about FIELD:
Great question to ask! I've been hiding in these woods long enough to know where the opportunities are. What type of work interests you?
[OPTIONS: Healthcare | Education | Government | Retail | Not sure]

Asking about EXPERIENCE (user said healthcare):
Healthcare is huge here! Are you just starting out or do you have experience?
[OPTIONS: Just starting out | Some experience | Very experienced]

Asking about SCHEDULE (user said entry-level):
Entry-level, got it! Full-time or part-time work?
[OPTIONS: Full-time | Part-time | Either works]

AFTER PROFILING COMPLETE (all 3 answered) - YOU MUST START WITH [SHOW_JOBS]:
[SHOW_JOBS]
Perfect! Entry-level healthcare, full-time. I've tracked down some opportunities from my hideout.
[OPTIONS: More jobs | Part-time instead | Different field]

CRITICAL: When all 3 questions are answered, your response MUST begin with [SHOW_JOBS] on its own line. Without this marker, NO job cards will appear!

Example correct response after profiling:
[SHOW_JOBS]
Full-time education, entry-level - got it! Here's what I found for you.
[OPTIONS: More jobs | Part-time instead | Different field]

LOCAL INFO:
- Major employers: Providence Hospital, Cal Poly Humboldt, Open Door Health, County of Humboldt
- Healthcare and Education dominate the job market`;

    // Build conversation context
    let conversationContext = '';
    if (conversationHistory.length > 0) {
        conversationContext = '\n\nCONVERSATION SO FAR:\n' + 
            conversationHistory.map(msg => `${msg.role}: ${msg.content}`).join('\n');
    }

    const prompt = `${systemPrompt}
${conversationContext}

AVAILABLE JOBS: ${context}

USER'S LATEST MESSAGE: ${query}

Remember: Ask ONE profiling question if you don't know their field/experience/schedule yet. NEVER list jobs in your text - job cards appear separately.`;

    try {
        const result = await model.generateContent({
            contents: [{ role: 'user', parts: [{ text: prompt }] }],
            generationConfig: {
                maxOutputTokens: 150, // Keep responses short
                temperature: 0.7,     // Balanced creativity
            }
        });
        const response = await result.response;
        return response.text();
    } catch (error) {
        console.error('Gemini API error:', error);
        throw new Error('Failed to generate response');
    }
}

/**
 * Main handler
 */
exports.handler = async (event, context) => {
    // CORS headers
    const headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Content-Type': 'application/json'
    };
    
    // Handle preflight
    if (event.httpMethod === 'OPTIONS') {
        return { statusCode: 200, headers, body: '' };
    }
    
    // Only allow POST
    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            headers,
            body: JSON.stringify({ error: 'Method not allowed' })
        };
    }
    
    try {
        // Parse request
        const body = JSON.parse(event.body || '{}');
        const query = (body.query || '').trim();
        const conversationHistory = body.history || []; // Optional conversation history
        
        if (!query) {
            return {
                statusCode: 400,
                headers,
                body: JSON.stringify({ error: 'No query provided' })
            };
        }
        
        if (query.length > 500) {
            return {
                statusCode: 400,
                headers,
                body: JSON.stringify({ error: 'Query too long (max 500 characters)' })
            };
        }
        
        // Content moderation - check for inappropriate content FIRST
        if (containsInappropriateContent(query)) {
            return {
                statusCode: 200,
                headers,
                body: JSON.stringify({
                    response: getModeratedResponse(),
                    jobs: [],
                    quickActions: [],
                    totalMatches: 0,
                    moderated: true
                })
            };
        }
        
        // Check cache first (keeps API costs down)
        // Note: We skip cache if there's conversation history for personalized responses
        if (conversationHistory.length === 0) {
            const cachedResponse = getCachedResponse(query);
            if (cachedResponse) {
                return {
                    statusCode: 200,
                    headers,
                    body: JSON.stringify({
                        response: cachedResponse,
                        cached: true
                    })
                };
            }
        }
        
        // Check for API key
        const apiKey = process.env.GEMINI_API_KEY;
        if (!apiKey) {
            return {
                statusCode: 500,
                headers,
                body: JSON.stringify({ error: 'API not configured' })
            };
        }
        
        // Load jobs data
        const jobs = await loadJobsData();
        
        // Build a combined query from conversation history for better job matching
        // This ensures earlier choices (like "Education") are included in the search
        let combinedQuery = query;
        if (conversationHistory.length > 0) {
            const userMessages = conversationHistory
                .filter(msg => msg.role === 'user')
                .map(msg => msg.content)
                .join(' ');
            combinedQuery = userMessages + ' ' + query;
        }
        
        // Get previously shown job titles from frontend to avoid repeating them
        const previouslyShownJobs = (body.shownJobTitles && Array.isArray(body.shownJobTitles)) 
            ? body.shownJobTitles 
            : [];
        
        // Find relevant jobs using the combined context (limit to 5), excluding already shown jobs
        const relevantJobs = findRelevantJobs(jobs, combinedQuery, 5, previouslyShownJobs);
        
        // Build context
        const jobContext = buildContext(relevantJobs, jobs.length);
        
        // Generate response with conversation history
        let aiResponse = await generateResponse(query, jobContext, apiKey, relevantJobs, conversationHistory);
        
        // Check if AI is ready to show jobs (profiling complete)
        // AI includes [SHOW_JOBS] marker when user has answered field + experience + schedule
        const showJobs = aiResponse.includes('[SHOW_JOBS]');
        
        // Remove the SHOW_JOBS marker from response
        aiResponse = aiResponse.replace(/\[SHOW_JOBS\]/gi, '').trim();
        
        // Remove any quotation marks wrapping the entire response
        aiResponse = aiResponse.replace(/^["']|["']$/g, '').trim();
        
        // Parse quick reply options from AI response
        // Format: [OPTIONS: Option1 | Option2 | Option3]
        let quickActions = [];
        const optionsMatch = aiResponse.match(/\[OPTIONS:\s*([^\]]+)\]/i);
        if (optionsMatch) {
            const optionsText = optionsMatch[1];
            quickActions = optionsText.split('|').map(opt => ({
                label: opt.trim(),
                query: opt.trim()
            })).filter(opt => opt.label.length > 0);
            
            // Remove the OPTIONS line from the response
            aiResponse = aiResponse.replace(/\[OPTIONS:\s*[^\]]+\]/gi, '').trim();
        }
        
        // Only format jobs if profiling is complete (SHOW_JOBS marker was present)
        let formattedJobs = [];
        if (showJobs) {
            formattedJobs = relevantJobs.slice(0, 3).map(job => {
                const employerSlug = generateSlug(job.employer);
                
                // Format salary for display
                let salaryDisplay = job.salary || '';
                if (job.salary_min && job.salary_max) {
                    const type = job.salary_type === 'hourly' ? '/hr' : '/yr';
                    if (job.salary_min === job.salary_max) {
                        salaryDisplay = `$${job.salary_min.toLocaleString()}${type}`;
                    } else {
                        salaryDisplay = `$${job.salary_min.toLocaleString()} - $${job.salary_max.toLocaleString()}${type}`;
                    }
                }
                
                return {
                    title: job.title,
                    employer: job.employer,
                    location: job.location,
                    salary: salaryDisplay,
                    category: job.category,
                    classification: job.classification || null,
                    url: `/employer/${employerSlug}/`,  // Link to Humboldt Jobs employer page
                    externalUrl: job.url,  // Keep original for reference
                    employmentType: job.job_type || null,
                    experienceLevel: job.experience_level || null,
                    educationRequired: job.education_required || null,
                    isRemote: job.is_remote || false,
                    department: job.department || null,
                    descriptionSnippet: job.description ? job.description.substring(0, 150) : null,
                    postedDate: job.posted_date || null
                };
            });
        }
        
        // Cache the cleaned response
        cacheResponse(query, aiResponse);
        
        return {
            statusCode: 200,
            headers,
            body: JSON.stringify({
                response: aiResponse,
                jobs: formattedJobs,
                quickActions: quickActions,
                totalMatches: relevantJobs.length,
                cached: false
            })
        };
        
    } catch (error) {
        console.error('Chat function error:', error);
        
        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({
                error: 'Something went wrong. Please try again.'
            })
        };
    }
};
