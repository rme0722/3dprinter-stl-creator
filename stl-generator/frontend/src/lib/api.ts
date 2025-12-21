import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface Project {
  id: string
  user_id: string
  name: string
  description?: string
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  project_id: string
  pipeline_type: 'SCAN' | 'RELIEF' | 'GENERATIVE'
  state: 'DRAFT' | 'SUBMITTED' | 'VALIDATING' | 'ACTION_REQUIRED' | 'QUEUED' | 'RUNNING' | 'REVIEW_REQUIRED' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
  hold_reason?: string
  config: Record<string, any>
  model_preset_id?: string
  printer_profile_id: string
  submitted_at?: string
  completed_at?: string
  error_code?: string
  error_message?: string
  safety_status?: 'PASS' | 'BLOCK' | 'REVIEW'
  safety_summary?: Record<string, any>
  quality_score?: number
  quality_score_version?: string
  quality_summary?: {
    input_quality: number
    reconstruction_confidence: number
    printability_risk: number
    notes?: string[]
  }
  created_at: string
  updated_at: string
}

export interface Artifact {
  id: string
  job_id: string
  project_id: string
  artifact_type: string
  format: string
  uri: string
  sha256: string
  size_bytes: number
  version: number
  label?: string
  metadata?: Record<string, any>
  created_at: string
  updated_at: string
}

export const api = {
  projects: {
    list: async (): Promise<Project[]> => {
      const { data } = await apiClient.get('/projects')
      return data
    },
    get: async (id: string): Promise<Project> => {
      const { data } = await apiClient.get(`/projects/${id}`)
      return data
    },
    create: async (project: { name: string; description?: string }): Promise<Project> => {
      const { data } = await apiClient.post('/projects', project)
      return data
    },
    update: async (id: string, project: Partial<Project>): Promise<Project> => {
      const { data } = await apiClient.patch(`/projects/${id}`, project)
      return data
    },
    delete: async (id: string): Promise<void> => {
      await apiClient.delete(`/projects/${id}`)
    },
  },
  
  jobs: {
    list: async (projectId: string): Promise<Job[]> => {
      const { data } = await apiClient.get(`/projects/${projectId}/jobs`)
      return data
    },
    get: async (jobId: string): Promise<Job> => {
      const { data } = await apiClient.get(`/jobs/${jobId}`)
      return data
    },
    create: async (projectId: string, job: {
      pipeline_type: 'SCAN' | 'RELIEF' | 'GENERATIVE'
      printer_profile_id: string
      model_preset_id?: string
      config?: Record<string, any>
    }): Promise<Job> => {
      const { data } = await apiClient.post(`/projects/${projectId}/jobs`, job)
      return data
    },
    submit: async (jobId: string): Promise<Job> => {
      const { data } = await apiClient.post(`/jobs/${jobId}/submit`)
      return data
    },
    cancel: async (jobId: string): Promise<Job> => {
      const { data } = await apiClient.post(`/jobs/${jobId}/cancel`)
      return data
    },
    resume: async (jobId: string, actionData?: Record<string, any>): Promise<Job> => {
      const { data } = await apiClient.post(`/jobs/${jobId}/resume`, actionData)
      return data
    },
  },
  
  artifacts: {
    list: async (jobId: string): Promise<Artifact[]> => {
      const { data } = await apiClient.get(`/jobs/${jobId}/artifacts`)
      return data
    },
    get: async (artifactId: string): Promise<Artifact> => {
      const { data } = await apiClient.get(`/artifacts/${artifactId}`)
      return data
    },
    getDownloadUrl: async (artifactId: string): Promise<{ download_url: string; expires_in: number }> => {
      const { data } = await apiClient.get(`/artifacts/${artifactId}/download-url`)
      return data
    },
  },
  
  uploads: {
    createSession: async (params: {
      job_id: string
      artifact_type: string
      files: Array<{
        filename: string
        content_type: string
        size_bytes: number
        sha256: string
      }>
    }): Promise<{
      upload_session_id: string
      files: Array<{
        filename: string
        put_url: string
        artifact_id: string
      }>
    }> => {
      const { data } = await apiClient.post('/uploads', params)
      return data
    },
    completeSession: async (sessionId: string, jobId: string): Promise<void> => {
      await apiClient.post(`/uploads/${sessionId}/complete`, { job_id: jobId })
    },
  },
}
