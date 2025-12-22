'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { 
  ArrowLeft, 
  Plus, 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  Loader2,
  ImageIcon,
  Sparkles,
  Camera
} from 'lucide-react'
import { api, Job } from '@/lib/api'
import { CreateJobDialog } from '@/components/create-job-dialog'

const stateColors: Record<Job['state'], string> = {
  DRAFT: 'bg-gray-500',
  SUBMITTED: 'bg-blue-500',
  VALIDATING: 'bg-yellow-500',
  ACTION_REQUIRED: 'bg-orange-500',
  QUEUED: 'bg-blue-400',
  RUNNING: 'bg-blue-600',
  REVIEW_REQUIRED: 'bg-purple-500',
  SUCCEEDED: 'bg-green-500',
  FAILED: 'bg-red-500',
  CANCELLED: 'bg-gray-400',
}

const stateIcons: Record<Job['state'], React.ReactNode> = {
  DRAFT: <Clock className="h-4 w-4" />,
  SUBMITTED: <Loader2 className="h-4 w-4 animate-spin" />,
  VALIDATING: <Loader2 className="h-4 w-4 animate-spin" />,
  ACTION_REQUIRED: <AlertCircle className="h-4 w-4" />,
  QUEUED: <Clock className="h-4 w-4" />,
  RUNNING: <Loader2 className="h-4 w-4 animate-spin" />,
  REVIEW_REQUIRED: <AlertCircle className="h-4 w-4" />,
  SUCCEEDED: <CheckCircle className="h-4 w-4" />,
  FAILED: <XCircle className="h-4 w-4" />,
  CANCELLED: <XCircle className="h-4 w-4" />,
}

const pipelineIcons: Record<Job['pipeline_type'], React.ReactNode> = {
  RELIEF: <ImageIcon className="h-5 w-5" />,
  SCAN: <Camera className="h-5 w-5" />,
  GENERATIVE: <Sparkles className="h-5 w-5" />,
}

const pipelineNames: Record<Job['pipeline_type'], string> = {
  RELIEF: 'Relief Pipeline',
  SCAN: 'Multi-Photo Scan',
  GENERATIVE: 'Generative Minis',
}

export default function ProjectPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string
  const [createJobOpen, setCreateJobOpen] = useState(false)
  
  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.projects.get(projectId),
  })
  
  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs', projectId],
    queryFn: () => api.jobs.list(projectId),
  })

  if (projectLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted rounded w-1/4" />
          <div className="h-4 bg-muted rounded w-1/2" />
        </div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>Project not found</CardTitle>
            <CardDescription>
              The project you&apos;re looking for doesn&apos;t exist or has been deleted.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/">
              <Button>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Projects
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Link href="/" className="text-muted-foreground hover:text-foreground inline-flex items-center mb-4">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Projects
        </Link>
        
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold">{project.name}</h1>
            {project.description && (
              <p className="text-muted-foreground mt-1">{project.description}</p>
            )}
            <p className="text-sm text-muted-foreground mt-2">
              Created {new Date(project.created_at).toLocaleDateString()}
            </p>
          </div>
          <Button onClick={() => setCreateJobOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Job
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Jobs</h2>
        
        {jobsLoading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map(i => (
              <Card key={i} className="animate-pulse">
                <CardHeader className="space-y-2">
                  <div className="h-6 bg-muted rounded w-3/4" />
                  <div className="h-4 bg-muted rounded w-1/2" />
                </CardHeader>
              </Card>
            ))}
          </div>
        ) : !jobs || jobs.length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle>No jobs yet</CardTitle>
              <CardDescription>
                Create a job to start processing your images into 3D models.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => setCreateJobOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create First Job
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {jobs.map((job) => (
              <Card key={job.id} className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      {pipelineIcons[job.pipeline_type]}
                      <span className="text-sm">{pipelineNames[job.pipeline_type]}</span>
                    </div>
                    <div className={`flex items-center gap-1 text-white text-xs px-2 py-1 rounded-full ${stateColors[job.state]}`}>
                      {stateIcons[job.state]}
                      <span>{job.state.replace('_', ' ')}</span>
                    </div>
                  </div>
                  <CardTitle className="text-lg mt-2">
                    Job {job.id.slice(-8)}
                  </CardTitle>
                  <CardDescription>
                    {job.hold_reason || `Created ${new Date(job.created_at).toLocaleDateString()}`}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {job.quality_score !== undefined && job.quality_score !== null && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Quality Score</span>
                        <span className={`font-medium ${
                          job.quality_score >= 0.8 ? 'text-green-500' :
                          job.quality_score >= 0.6 ? 'text-yellow-500' : 'text-red-500'
                        }`}>
                          {(job.quality_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                    {job.error_message && (
                      <p className="text-sm text-red-500">{job.error_message}</p>
                    )}
                    <Link href={`/projects/${projectId}/jobs/${job.id}`}>
                      <Button variant="outline" className="w-full mt-2">
                        View Details
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <CreateJobDialog
        projectId={projectId}
        open={createJobOpen}
        onOpenChange={setCreateJobOpen}
      />
    </div>
  )
}
