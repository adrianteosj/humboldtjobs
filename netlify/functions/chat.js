/**
 * Netlify Function: AI Chat for Humboldt Jobs
 * Uses Google Gemini API (free tier) with rate limiting and caching
 */

const { GoogleGenerativeAI } = require('@google/generative-ai');

// In-memory cache for responses (persists across warm function instances)
const responseCache = new Map();
const CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours
const MAX_CACHE_SIZE = 100;

// In-memory rate limiting (per IP)
const rateLimits = new Map();
const DAILY_LIMIT = 10;

// Jobs data (loaded once per function instance)
let jobsData = null;

/**
 * Load jobs data from the static JSON file
 */
async function loadJobsData() {
    if (jobsData) return jobsData;
    
    try {
        // Fetch from the deployed static site
        const response = await fetch('https://jobsinhumboldt.com/static/jobs.json');
        if (response.ok) {
            jobsData = await response.json();
            return jobsData;
        }
    } catch (error) {
        console.error('Failed to fetch jobs.json:', error);
    }
    
    // Fallback: return empty array
    return [];
}

/**
 * Check and update rate limit for an IP
 */
function checkRateLimit(ip) {
    const today = new Date().toDateString();
    const key = `${ip}:${today}`;
    
    // Clean old entries
    for (const [k, v] of rateLimits.entries()) {
        if (!k.includes(today)) {
            rateLimits.delete(k);
        }
    }
    
    const current = rateLimits.get(key) || 0;
    
    if (current >= DAILY_LIMIT) {
        return { allowed: false, remaining: 0 };
    }
    
    rateLimits.set(key, current + 1);
    return { allowed: true, remaining: DAILY_LIMIT - current - 1 };
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
 * Score job relevance to query
 */
function scoreJob(job, keywords) {
    let score = 0;
    const titleLower = (job.title || '').toLowerCase();
    const employerLower = (job.employer || '').toLowerCase();
    const categoryLower = (job.category || '').toLowerCase();
    const locationLower = (job.location || '').toLowerCase();
    const salaryLower = (job.salary || '').toLowerCase();
    
    for (const keyword of keywords) {
        // Title matches are most important
        if (titleLower.includes(keyword)) score += 10;
        // Category matches
        if (categoryLower.includes(keyword)) score += 5;
        // Employer matches
        if (employerLower.includes(keyword)) score += 3;
        // Location matches
        if (locationLower.includes(keyword)) score += 2;
    }
    
    // Boost jobs with salary info
    if (job.salary && job.salary.trim()) score += 1;
    
    return score;
}

/**
 * Find relevant jobs for the query
 */
function findRelevantJobs(jobs, query, limit = 10) {
    const keywords = extractKeywords(query);
    
    // Special handling for common query patterns
    const queryLower = query.toLowerCase();
    
    // Highest paying query
    if (queryLower.includes('highest pay') || queryLower.includes('best pay') || 
        queryLower.includes('most pay') || queryLower.includes('top pay') ||
        queryLower.includes('highest salary') || queryLower.includes('best salary')) {
        return jobs
            .filter(job => job.salary && job.salary.trim())
            .sort((a, b) => {
                const aMax = extractMaxSalary(a.salary);
                const bMax = extractMaxSalary(b.salary);
                return bMax - aMax;
            })
            .slice(0, limit);
    }
    
    // If no meaningful keywords, return random sample
    if (keywords.length === 0) {
        return jobs.slice(0, limit);
    }
    
    // Score and sort jobs
    const scored = jobs.map(job => ({
        job,
        score: scoreJob(job, keywords)
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
 * Build compact context for the AI
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
        if (job.location) context += `\n   Location: ${job.location}`;
        if (job.salary && job.salary.trim()) context += `\n   Salary: ${job.salary}`;
        context += `\n   URL: ${job.url}`;
        context += '\n\n';
    });
    
    context += `Total jobs available on the site: ${totalJobs}`;
    
    return context;
}

/**
 * Generate AI response using Gemini
 */
async function generateResponse(query, context, apiKey) {
    const genAI = new GoogleGenerativeAI(apiKey);
    const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });
    
    const systemPrompt = `You are a helpful job search assistant for Humboldt Jobs (jobsinhumboldt.com), a job board for Humboldt County, California.

Your role:
- Help users find relevant jobs from the listings provided
- Answer questions about job opportunities, salaries, employers, and categories
- Be concise, friendly, and helpful
- When listing jobs, include key details like employer, salary (if available), and location
- If asked about something not in the job data, politely explain you can only help with jobs listed on the site
- Encourage users to visit the full job listing URLs for complete details and to apply
- Keep responses brief but informative (2-3 paragraphs max)

Important: Only reference jobs from the data provided. Do not make up jobs or details.`;

    const prompt = `${systemPrompt}

Here is the current job data:
${context}

User question: ${query}

Please provide a helpful response:`;

    try {
        const result = await model.generateContent(prompt);
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
        
        // Get client IP for rate limiting
        const ip = event.headers['x-forwarded-for']?.split(',')[0]?.trim() || 
                   event.headers['client-ip'] || 
                   'unknown';
        
        // Check rate limit
        const rateCheck = checkRateLimit(ip);
        if (!rateCheck.allowed) {
            return {
                statusCode: 429,
                headers,
                body: JSON.stringify({
                    error: 'Daily limit reached. Try again tomorrow!',
                    remaining: 0
                })
            };
        }
        
        // Check cache first
        const cachedResponse = getCachedResponse(query);
        if (cachedResponse) {
            return {
                statusCode: 200,
                headers,
                body: JSON.stringify({
                    response: cachedResponse,
                    remaining: rateCheck.remaining,
                    cached: true
                })
            };
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
        
        // Find relevant jobs
        const relevantJobs = findRelevantJobs(jobs, query, 10);
        
        // Build context
        const jobContext = buildContext(relevantJobs, jobs.length);
        
        // Generate response
        const aiResponse = await generateResponse(query, jobContext, apiKey);
        
        // Cache the response
        cacheResponse(query, aiResponse);
        
        return {
            statusCode: 200,
            headers,
            body: JSON.stringify({
                response: aiResponse,
                remaining: rateCheck.remaining,
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
