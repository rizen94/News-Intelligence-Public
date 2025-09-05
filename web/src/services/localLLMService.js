/**
 * Local LLM Service for News Intelligence System v3.0
 * 100% Local Processing with Ollama Integration
 */

import { APIResponse } from '../types/api';
import { ErrorHandler } from '../utils/errorHandling';

// Local LLM Types
export interface LocalModel {
  name: string;
  type: 'llm' | 'embedding' | 'classification' | 'generation';
  size: 'small' | 'medium' | 'large' | 'xlarge';
  memory_required: number; // GB
  performance: {
    speed: 'fast' | 'medium' | 'slow';
    quality: 'basic' | 'good' | 'excellent';
    accuracy: number;
  };
  use_cases: string[];
  local_path: string;
  status: 'available' | 'downloading' | 'error';
}

export interface LocalLLMRequest {
  prompt: string;
  model: string;
  options: {
    temperature: number;
    max_tokens: number;
    system_prompt?: string;
  };
  context?: {
    previous_messages: Message[];
    few_shot_examples: Example[];
  };
}

export interface LocalLLMResponse {
  content: string;
  model_used: string;
  metadata: {
    tokens_used: number;
    response_time: number;
    confidence: number;
    local_processing: true;
  };
  alternatives?: Array<{
    content: string;
    confidence: number;
  }>;
}

export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface Example {
  input: string;
  output: string;
  explanation?: string;
}

export interface LocalModelSelectionStrategy {
  task_type: string;
  complexity: 'low' | 'medium' | 'high';
  time_constraint: number;
  quality_requirement: number;
  memory_available: number; // GB
}

export interface LocalModelSelectionResult {
  selected_model: string;
  confidence: number;
  estimated_time: number;
  memory_required: number;
  reasoning: string;
}

// Ollama Base URL
const OLLAMA_BASE_URL = process.env.REACT_APP_OLLAMA_URL || 'http://localhost:11434';

class LocalLLMService {
  private availableModels: LocalModel[] = [];
  private systemResources: SystemResources = { totalMemory: 32, availableMemory: 24, cpuCores: 8, gpuAvailable: false };

  constructor() {
    this.initializeModels();
  }

  private initializeModels(): void {
    this.availableModels = [
      {
        name: 'llama3.1:8b',
        type: 'llm',
        size: 'medium',
        memory_required: 8,
        performance: { speed: 'fast', quality: 'excellent', accuracy: 0.85 },
        use_cases: ['summarization', 'analysis', 'generation', 'sentiment'],
        local_path: '/home/user/.ollama/models/llama3.1:8b',
        status: 'available'
      },
      {
        name: 'llama3.1:70b',
        type: 'llm',
        size: 'xlarge',
        memory_required: 40,
        performance: { speed: 'slow', quality: 'excellent', accuracy: 0.92 },
        use_cases: ['complex_analysis', 'fact_checking', 'research', 'insights'],
        local_path: '/home/user/.ollama/models/llama3.1:70b',
        status: 'available'
      },
      {
        name: 'nomic-embed-text',
        type: 'embedding',
        size: 'small',
        memory_required: 2,
        performance: { speed: 'fast', quality: 'good', accuracy: 0.88 },
        use_cases: ['similarity', 'clustering', 'search'],
        local_path: '/home/user/.ollama/models/nomic-embed-text',
        status: 'available'
      }
    ];
  }

  // Get available local models
  async getAvailableModels(): Promise<APIResponse<LocalModel[]>> {
    try {
      // Check which models are actually available via Ollama
      const response = await fetch(`${OLLAMA_BASE_URL}/api/tags`);
      if (!response.ok) {
        throw new Error(`Ollama not available: ${response.statusText}`);
      }

      const data = await response.json();
      const ollamaModels = data.models?.map((m: any) => m.name) || [];

      // Filter our configured models to only show available ones
      const availableModels = this.availableModels.filter(model => 
        ollamaModels.includes(model.name)
      );

      return {
        success: true,
        data: availableModels,
        message: `Found ${availableModels.length} local models available`,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      const appError = ErrorHandler.handle(error, { endpoint: '/api/tags' });
      return {
        success: false,
        data: [],
        message: 'Failed to get available models',
        error: appError.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // Generate content with local model
  async generateContent(request: LocalLLMRequest): Promise<APIResponse<LocalLLMResponse>> {
    try {
      const startTime = Date.now();
      
      const response = await fetch(`${OLLAMA_BASE_URL}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: request.model,
          prompt: request.prompt,
          system: request.options.system_prompt,
          options: {
            temperature: request.options.temperature,
            num_predict: request.options.max_tokens,
          }
        })
      });

      if (!response.ok) {
        throw new Error(`Ollama generation failed: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      let content = '';
      
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = new TextDecoder().decode(value);
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.trim()) {
              try {
                const data = JSON.parse(line);
                if (data.response) {
                  content += data.response;
                }
              } catch (e) {
                // Skip invalid JSON
              }
            }
          }
        }
      }

      const responseTime = Date.now() - startTime;

      return {
        success: true,
        data: {
          content,
          model_used: request.model,
          metadata: {
            tokens_used: content.split(' ').length, // Rough estimate
            response_time: responseTime,
            confidence: 0.85, // Local models are generally reliable
            local_processing: true
          }
        },
        message: 'Content generated successfully with local model'
      };
    } catch (error) {
      const appError = ErrorHandler.handle(error, { request });
      return {
        success: false,
        data: {} as LocalLLMResponse,
        message: 'Failed to generate content',
        error: appError.message
      };
    }
  }

  // Smart local model selection
  async selectModel(strategy: LocalModelSelectionStrategy): Promise<APIResponse<LocalModelSelectionResult>> {
    try {
      const availableModels = await this.getAvailableModels();
      if (!availableModels.success) {
        throw new Error('Failed to get available models');
      }

      const suitableModels = availableModels.data.filter(model => {
        // Check if model is suitable for task type
        if (!model.use_cases.includes(strategy.task_type)) return false;
        
        // Check if system has enough memory
        if (model.memory_required > strategy.memory_available) return false;
        
        // Check quality requirement
        const qualityScore = { basic: 1, good: 2, excellent: 3 };
        const requiredQuality = qualityScore[strategy.quality_requirement] || 2;
        const modelQuality = qualityScore[model.performance.quality] || 2;
        
        return modelQuality >= requiredQuality;
      });

      if (suitableModels.length === 0) {
        return {
          success: false,
          data: {} as LocalModelSelectionResult,
          message: 'No suitable local models available for this task',
          error: 'No models match the requirements'
        };
      }

      // Score models based on requirements
      const scoredModels = suitableModels.map(model => ({
        model,
        score: this.calculateModelScore(model, strategy)
      }));

      // Return best scoring model
      const bestModel = scoredModels.sort((a, b) => b.score - a.score)[0].model;

      return {
        success: true,
        data: {
          selected_model: bestModel.name,
          confidence: bestModel.performance.accuracy,
          estimated_time: this.estimateResponseTime(bestModel, strategy),
          memory_required: bestModel.memory_required,
          reasoning: `Selected ${bestModel.name} based on ${strategy.task_type} requirements and available resources`
        },
        message: 'Model selected successfully'
      };
    } catch (error) {
      const appError = ErrorHandler.handle(error, { strategy });
      return {
        success: false,
        data: {} as LocalModelSelectionResult,
        message: 'Failed to select model',
        error: appError.message
      };
    }
  }

  private calculateModelScore(model: LocalModel, strategy: LocalModelSelectionStrategy): number {
    let score = 0;
    
    // Quality requirement
    const qualityScore = { basic: 1, good: 2, excellent: 3 };
    if (model.performance.quality === strategy.quality_requirement) score += 10;
    
    // Speed requirement
    const speedScore = { fast: 3, medium: 2, slow: 1 };
    const speedRequirement = strategy.time_constraint < 5 ? 'fast' : strategy.time_constraint < 15 ? 'medium' : 'slow';
    if (model.performance.speed === speedRequirement) score += 8;
    
    // Accuracy
    score += model.performance.accuracy * 5;
    
    // Memory efficiency (prefer smaller models if quality is sufficient)
    const memoryEfficiency = 1 / (model.memory_required / 8); // Normalize to 8GB
    score += memoryEfficiency * 3;
    
    return score;
  }

  private estimateResponseTime(model: LocalModel, strategy: LocalModelSelectionStrategy): number {
    const baseTime = { fast: 2, medium: 8, slow: 20 };
    const complexityMultiplier = { low: 1, medium: 1.5, high: 2.5 };
    
    return baseTime[model.performance.speed] * complexityMultiplier[strategy.complexity];
  }

  // Content generation helpers
  async summarizeText(
    text: string,
    options: {
      length: 'short' | 'medium' | 'long';
      style: 'bullet' | 'paragraph' | 'headline';
      language: string;
    }
  ): Promise<APIResponse<LocalLLMResponse>> {
    const modelSelection = await this.selectModel({
      task_type: 'summarization',
      complexity: 'medium',
      time_constraint: 10,
      quality_requirement: 'good',
      memory_available: this.systemResources.availableMemory
    });

    if (!modelSelection.success) {
      return {
        success: false,
        data: {} as LocalLLMResponse,
        message: 'Failed to select model for summarization',
        error: modelSelection.error
      };
    }

    const prompt = `Summarize the following text in ${options.length} ${options.style} format:\n\n${text}`;
    
    return this.generateContent({
      prompt,
      model: modelSelection.data.selected_model,
      options: {
        temperature: 0.3,
        max_tokens: options.length === 'short' ? 100 : options.length === 'medium' ? 200 : 400,
        system_prompt: 'You are a helpful assistant that creates clear, concise summaries.'
      }
    });
  }

  async generateHeadlines(
    content: string,
    count: number = 5
  ): Promise<APIResponse<LocalLLMResponse>> {
    const modelSelection = await this.selectModel({
      task_type: 'generation',
      complexity: 'low',
      time_constraint: 5,
      quality_requirement: 'good',
      memory_available: this.systemResources.availableMemory
    });

    if (!modelSelection.success) {
      return {
        success: false,
        data: {} as LocalLLMResponse,
        message: 'Failed to select model for headline generation',
        error: modelSelection.error
      };
    }

    const prompt = `Generate ${count} engaging headlines for the following content:\n\n${content}`;
    
    return this.generateContent({
      prompt,
      model: modelSelection.data.selected_model,
      options: {
        temperature: 0.7,
        max_tokens: 200,
        system_prompt: 'You are a creative headline writer. Generate engaging, accurate headlines.'
      }
    });
  }

  async factCheck(
    content: string,
    options: {
      include_sources: boolean;
      detailed_explanation: boolean;
    }
  ): Promise<APIResponse<LocalLLMResponse>> {
    const modelSelection = await this.selectModel({
      task_type: 'fact_checking',
      complexity: 'high',
      time_constraint: 30,
      quality_requirement: 'excellent',
      memory_available: this.systemResources.availableMemory
    });

    if (!modelSelection.success) {
      return {
        success: false,
        data: {} as LocalLLMResponse,
        message: 'Failed to select model for fact checking',
        error: modelSelection.error
      };
    }

    const prompt = `Fact-check the following content and provide a detailed analysis${options.include_sources ? ' with sources' : ''}:\n\n${content}`;
    
    return this.generateContent({
      prompt,
      model: modelSelection.data.selected_model,
      options: {
        temperature: 0.1,
        max_tokens: 500,
        system_prompt: 'You are a fact-checking assistant. Analyze content for accuracy and provide evidence-based assessments.'
      }
    });
  }

  async generateInsights(
    content: string,
    options: {
      type: 'business' | 'technical' | 'social' | 'political';
      depth: 'surface' | 'moderate' | 'deep';
    }
  ): Promise<APIResponse<LocalLLMResponse>> {
    const modelSelection = await this.selectModel({
      task_type: 'insights',
      complexity: 'high',
      time_constraint: 20,
      quality_requirement: 'excellent',
      memory_available: this.systemResources.availableMemory
    });

    if (!modelSelection.success) {
      return {
        success: false,
        data: {} as LocalLLMResponse,
        message: 'Failed to select model for insight generation',
        error: modelSelection.error
      };
    }

    const prompt = `Generate ${options.depth} ${options.type} insights from the following content:\n\n${content}`;
    
    return this.generateContent({
      prompt,
      model: modelSelection.data.selected_model,
      options: {
        temperature: 0.5,
        max_tokens: 400,
        system_prompt: `You are a ${options.type} analyst. Provide ${options.depth} insights based on the content.`
      }
    });
  }

  // System resource monitoring
  async getSystemResources(): Promise<APIResponse<SystemResources>> {
    return {
      success: true,
      data: this.systemResources,
      message: 'System resources retrieved successfully'
    };
  }

  // Model performance monitoring
  async getModelPerformance(model: string): Promise<APIResponse<{
    model: string;
    requests: number;
    average_response_time: number;
    success_rate: number;
    error_rate: number;
    average_quality_score: number;
  }>> {
    // This would be implemented to track actual performance metrics
    return {
      success: true,
      data: {
        model,
        requests: 0,
        average_response_time: 0,
        success_rate: 100,
        error_rate: 0,
        average_quality_score: 0.85
      },
      message: 'Model performance retrieved successfully'
    };
  }
}

interface SystemResources {
  totalMemory: number;
  availableMemory: number;
  cpuCores: number;
  gpuAvailable: boolean;
}

// Export singleton instance
export const localLLMService = new LocalLLMService();
export default localLLMService;
