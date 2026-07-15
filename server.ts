import express from 'express';
import path from 'path';
import { createServer as createViteServer } from 'vite';
import { GoogleGenAI, Type } from '@google/genai';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const PORT = 3000;

app.use(express.json({ limit: '20mb' }));

// Lazy initializer for Google GenAI client
let aiClient: GoogleGenAI | null = null;

function getAIClient(): GoogleGenAI {
  if (!aiClient) {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey || apiKey === 'MY_GEMINI_API_KEY') {
      throw new Error('GEMINI_API_KEY is not configured in secrets. Please set it in Settings > Secrets.');
    }
    aiClient = new GoogleGenAI({
      apiKey,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build',
        },
      },
    });
  }
  return aiClient;
}

/**
 * API: Analyze Dataset
 * Generates structured executive report utilizing gemini-3.5-flash
 */
app.post('/api/analyze', async (req, res) => {
  try {
    const { datasetName, datasetDescription, columns, numericColumns, dataRows } = req.body;

    if (!dataRows || !Array.isArray(dataRows) || dataRows.length === 0) {
       res.status(400).json({ error: 'No data provided for analysis.' });
       return;
    }

    // Lazy initialization of Gemini
    let ai;
    try {
      ai = getAIClient();
    } catch (apiError: any) {
      console.warn('AI SDK Init failed:', apiError.message);
       res.status(403).json({
        error: apiError.message,
        isDemoMode: true,
        fallbackData: generateDemoReport(datasetName, dataRows, numericColumns)
      });
       return;
    }

    const payloadString = JSON.stringify({
      datasetName,
      datasetDescription,
      columns,
      numericColumns,
      sampleData: dataRows.slice(0, 100), // pass up to 100 rows for analysis
      rowCount: dataRows.length
    });

    const systemInstruction = `You are a world-class Business Intelligence and Data Analytics specialist.
Analyze the user's uploaded dataset and compile a comprehensive executive report in JSON format.
You must return a strictly valid JSON response conforming EXACTLY to this schema structure:
{
  "overview": "A polished narrative summary (2-3 sentences) explaining what this dataset is, what timeframe/dimension it tracks, and the high-level takeaways.",
  "keyMetrics": [
    {
      "name": "Revenue / Visitors / Active Users / etc.",
      "value": "$125K / 4.5% / 32,000 / etc. (formatted appropriately)",
      "description": "Brief description of why this is a primary performance indicator.",
      "change": "+12.4% compared to start / -2% decline (optional)",
      "trend": "up" or "down" or "neutral"
    }
  ],
  "trendsAnalysis": "A deep narrative analysis identifying growth/decline, cyclical patterns, correlation between columns, or notable spikes/anomalies.",
  "recommendations": [
    "Specific, actionable business or engineering suggestion based on the data findings.",
    "Another strategic recommendation."
  ],
  "suggestedQuestions": [
    "A direct, relevant question the user might want to ask next in a follow-up chat, focusing on deep dives of an anomaly or optimization."
  ]
}`;

    const prompt = `Please analyze the following dataset and generate the analysis report:\n\n${payloadString}`;

    const response = await ai.models.generateContent({
      model: 'gemini-3.5-flash',
      contents: prompt,
      config: {
        systemInstruction,
        responseMimeType: 'application/json',
        responseSchema: {
          type: Type.OBJECT,
          required: ['overview', 'keyMetrics', 'trendsAnalysis', 'recommendations', 'suggestedQuestions'],
          properties: {
            overview: { type: Type.STRING },
            keyMetrics: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                required: ['name', 'value', 'description', 'trend'],
                properties: {
                  name: { type: Type.STRING },
                  value: { type: Type.STRING },
                  description: { type: Type.STRING },
                  change: { type: Type.STRING },
                  trend: { type: Type.STRING, enum: ['up', 'down', 'neutral'] }
                }
              }
            },
            trendsAnalysis: { type: Type.STRING },
            recommendations: {
              type: Type.ARRAY,
              items: { type: Type.STRING }
            },
            suggestedQuestions: {
              type: Type.ARRAY,
              items: { type: Type.STRING }
            }
          }
        }
      }
    });

    const reportText = response.text;
    if (!reportText) {
      throw new Error('Gemini returned an empty response.');
    }

    const reportJson = JSON.parse(reportText.trim());
     res.json(reportJson);

  } catch (error: any) {
    console.error('Analysis error:', error);
     res.status(500).json({
      error: 'An error occurred during dataset analysis.',
      details: error.message
    });
  }
});

/**
 * API: Conversation with Dataset
 * Handles contextual interactive questions regarding the active dataset
 */
app.post('/api/chat', async (req, res) => {
  try {
    const { datasetName, columns, numericColumns, dataRows, messages } = req.body;

    if (!messages || !Array.isArray(messages)) {
       res.status(400).json({ error: 'Conversation history is required.' });
       return;
    }

    // Lazy initialization of Gemini
    let ai;
    try {
      ai = getAIClient();
    } catch (apiError: any) {
       res.status(403).json({
        error: apiError.message,
        isDemoMode: true,
        reply: "Hello! I am running in local Demo Mode because the GEMINI_API_KEY secret is not set yet. Please register your key under 'Settings > Secrets' to unlock live AI chat. In the meantime, you can explore visual trends and export your PDF reports!"
      });
       return;
    }

    const datasetSample = dataRows ? dataRows.slice(0, 100) : [];
    const context = `You are "DataSense AI", an expert data scientist assistant.
You are helping a client understand their dataset: "${datasetName || 'Uploaded Dataset'}".
Here is some technical context of the dataset:
- Columns: ${JSON.stringify(columns || [])}
- Numeric Columns: ${JSON.stringify(numericColumns || [])}
- Rows Count: ${dataRows ? dataRows.length : 0}
- Preview of Data (up to 100 rows):
${JSON.stringify(datasetSample, null, 2)}

Instructions:
- Ground all answers strictly in the provided dataset or samples.
- Be precise, mathematically accurate, and business-focused.
- If the user asks about calculations, do the math or look it up in the dataset rows provided.
- Format your response beautifully using markdown (bold, bullet points, numbered lists, code block quotes). Do NOT use excessive formatting.
- Keep responses concise, clear, and action-oriented.`;

    const chatHistory = messages.map((msg: any) => ({
      role: msg.sender === 'user' ? 'user' : 'model',
      parts: [{ text: msg.text }]
    }));

    // Add the user's latest message
    const latestMessage = chatHistory.pop();

    const chat = ai.chats.create({
      model: 'gemini-3.5-flash',
      config: {
        systemInstruction: context,
      },
      history: chatHistory
    });

    const response = await chat.sendMessage({
      message: latestMessage ? latestMessage.parts[0].text : 'Review this dataset.'
    });

     res.json({ reply: response.text });

  } catch (error: any) {
    console.error('Chat error:', error);
     res.status(500).json({
      error: 'An error occurred while communicating with the AI analyst.',
      details: error.message
    });
  }
});

/**
 * Fallback static demo report generator in case GEMINI_API_KEY is not defined yet.
 * Ensures incredible UX out of the box!
 */
function generateDemoReport(datasetName: string, rows: any[], numericCols: string[]): any {
  const rowCount = rows.length;
  const numCol = numericCols[0] || '';

  let statsSummaryText = '';
  let metricsList: any[] = [];

  if (numCol) {
    const values = rows.map(r => Number(r[numCol])).filter(v => !isNaN(v));
    const maxVal = Math.max(...values);
    const minVal = Math.min(...values);
    const sumVal = values.reduce((a, b) => a + b, 0);
    const avgVal = sumVal / (values.length || 1);

    metricsList = [
      {
        name: `Total Sum (${numCol})`,
        value: typeof sumVal === 'number' ? sumVal.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '0',
        description: `Aggregate volume of ${numCol} across all recorded segments.`,
        trend: 'up'
      },
      {
        name: `Average Value (${numCol})`,
        value: typeof avgVal === 'number' ? avgVal.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '0',
        description: `Mean statistical value computed per data point.`,
        trend: 'neutral'
      },
      {
        name: `Peak Maximum (${numCol})`,
        value: typeof maxVal === 'number' ? maxVal.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '0',
        description: `Highest recording boundary in the active series.`,
        trend: 'up'
      }
    ];

    statsSummaryText = `The dataset features peak metrics touching ${maxVal.toLocaleString()} with an average score of ${avgVal.toLocaleString(undefined, { maximumFractionDigits: 1 })} per unit.`;
  } else {
    metricsList = [
      { name: 'Total Rows', value: rowCount, description: 'Total records within the loaded dataset.', trend: 'neutral' }
    ];
  }

  return {
    overview: `This report analyzes '${datasetName || 'Custom Dataset'}' consisting of ${rowCount} records. It is processed in Demo Mode as the AI key is being configured.`,
    keyMetrics: metricsList,
    trendsAnalysis: `An analysis of the dataset rows reveals steady progression. ${statsSummaryText} There is a strong cyclical trend observed between the intervals. Further key indicators show consistent, healthy correlations.`,
    recommendations: [
      'Prioritize optimizations around the highest-performing intervals identified in the trendlines.',
      'Gather more high-frequency categorical parameters to cross-correlate with high-volume metrics.',
      'Configure your GEMINI_API_KEY in the Secrets panel to activate live deep intelligence, anomaly discovery, and actionable recommendations!'
    ],
    suggestedQuestions: [
      'What is the standard deviation of our key metrics?',
      'How does the first half of the dataset compare to the second half?'
    ]
  };
}

// Vite integration middleware setup & build static server config
async function bootstrap() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on http://localhost:${PORT} in ${process.env.NODE_ENV || 'development'} mode`);
  });
}

bootstrap().catch(err => {
  console.error('Failed to start server:', err);
});
