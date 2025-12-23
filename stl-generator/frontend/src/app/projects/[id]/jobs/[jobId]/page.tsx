'use client'

import { useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ArrowLeft,
  Play,
  XCircle,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  ImageIcon,
  Sparkles,
  Camera,
  Download,
  Upload,
  X,
  FileImage
} from 'lucide-react'
import { api, Job, Artifact } from '@/lib/api'
import dynamic from 'next/dynamic'

const STLViewer = dynamic(
  () => import('@/components/stl-viewer').then(mod => mod.STLViewer),
  { ssr: false, loading: () => <div className="h-64 bg-muted rounded-lg animate-pulse" /> }
)

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

const stateDescriptions: Record<Job['state'], string> = {
  DRAFT: 'Job is in draft state. Upload files and submit to start processing.',
  SUBMITTED: 'Job has been submitted and is waiting to be processed.',
  VALIDATING: 'Validating uploaded files and job configuration.',
  ACTION_REQUIRED: 'User action is required to continue.',
  QUEUED: 'Job is queued and waiting for available workers.',
  RUNNING: 'Job is currently being processed.',
  REVIEW_REQUIRED: 'Review the preview and approve to continue.',
  SUCCEEDED: 'Job completed successfully!',
  FAILED: 'Job failed. Check error details below.',
  CANCELLED: 'Job was cancelled.',
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

function formatDateTime(dateString: string): string {
  const date = new Date(dateString)
  // Handle UTC timestamps from backend
  if (!dateString.endsWith('Z') && !dateString.includes('+')) {
    // Assume UTC if no timezone specified
    return new Date(dateString + 'Z').toLocaleString()
  }
  return date.toLocaleString()
}

export default function JobPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const projectId = params.id as string
  const jobId = params.jobId as string

  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [filePreviews, setFilePreviews] = useState<string[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files)
      setSelectedFiles(prev => [...prev, ...newFiles])

      // Create previews for new files
      const newPreviews = newFiles.map(file => URL.createObjectURL(file))
      setFilePreviews(prev => [...prev, ...newPreviews])
    }
  }

  const handleRemoveFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))

    // Revoke URL to avoid memory leaks
    if (filePreviews[index]) {
      URL.revokeObjectURL(filePreviews[index])
    }
    setFilePreviews(prev => prev.filter((_, i) => i !== index))

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const clearAllFiles = () => {
    selectedFiles.forEach((_, i) => {
      if (filePreviews[i]) URL.revokeObjectURL(filePreviews[i])
    })
    setSelectedFiles([])
    setFilePreviews([])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const { data: job, isLoading: jobLoading } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.jobs.get(jobId),
    refetchInterval: (query) => {
      // Poll more frequently for active jobs
      const state = query.state.data?.state
      if (state && ['SUBMITTED', 'VALIDATING', 'QUEUED', 'RUNNING'].includes(state)) {
        return 3000
      }
      return false
    },
  })

  const { data: artifacts } = useQuery({
    queryKey: ['artifacts', jobId, job?.state],
    queryFn: () => api.artifacts.list(jobId),
    enabled: !!job,
    // Refetch when job completes to get output artifacts
    refetchInterval: job?.state === 'SUCCEEDED' ? false :
      ['SUBMITTED', 'VALIDATING', 'QUEUED', 'RUNNING'].includes(job?.state || '') ? 3000 : false,
  })

  const [uploadProgress, setUploadProgress] = useState<{ current: number, total: number } | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploads.uploadFile(jobId, file, 'RAW_IMAGE'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artifacts', jobId], exact: false })
      setUploadError(null)
    },
    onError: (error: Error) => {
      setUploadError(error.message)
    },
  })

  const [submitError, setSubmitError] = useState<string | null>(null)

  const submitMutation = useMutation({
    mutationFn: async () => {
      console.log('Submit mutation starting, files:', selectedFiles.length)
      setSubmitError(null)

      // Upload files first if selected
      if (selectedFiles.length > 0) {
        setIsUploading(true)
        setUploadProgress({ current: 0, total: selectedFiles.length })

        try {
          // Upload sequentially to avoid overwhelming browser/connection
          // Could implement concurrent batches (e.g. 5 at a time) for speed
          for (let i = 0; i < selectedFiles.length; i++) {
            const file = selectedFiles[i]
            console.log(`Uploading file ${i + 1}/${selectedFiles.length}: ${file.name}`)

            // Determine artifact type based on pipeline
            // SCAN pipeline uses RAW_PHOTO for inputs
            const artifactType = job?.pipeline_type === 'SCAN' ? 'RAW_PHOTO' : 'RAW_IMAGE'

            await api.uploads.uploadFile(jobId, file, artifactType)
            setUploadProgress({ current: i + 1, total: selectedFiles.length })
          }
        } catch (error) {
          console.error("Upload failed", error)
          throw error
        } finally {
          setIsUploading(false)
          setUploadProgress(null)
        }
      } else {
        console.log('No new files selected for upload (assuming previously uploaded)')
      }
      // Then submit the job
      console.log('Submitting job:', jobId)
      const result = await api.jobs.submit(jobId)
      console.log('Submit result:', result)
      return result
    },
    onSuccess: () => {
      console.log('Submit successful, invalidating queries')
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
      queryClient.invalidateQueries({ queryKey: ['artifacts', jobId] })
      clearAllFiles()
    },
    onError: (error: Error) => {
      console.error('Submit error:', error)
      setSubmitError(error.message || 'Failed to submit job')
    },
  })

  const cancelMutation = useMutation({
    mutationFn: () => api.jobs.cancel(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
    },
  })

  if (jobLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted rounded w-1/4" />
          <div className="h-4 bg-muted rounded w-1/2" />
        </div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>Job not found</CardTitle>
            <CardDescription>
              The job you&apos;re looking for doesn&apos;t exist or has been deleted.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href={`/projects/${projectId}`}>
              <Button>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Project
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  const canSubmit = job.state === 'DRAFT'
  const canCancel = ['DRAFT', 'SUBMITTED', 'VALIDATING', 'QUEUED', 'RUNNING'].includes(job.state)
  const isProcessing = ['SUBMITTED', 'VALIDATING', 'QUEUED', 'RUNNING'].includes(job.state)
  const isCompleted = ['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(job.state)

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6">
        <Link
          href={`/projects/${projectId}`}
          className="text-muted-foreground hover:text-foreground inline-flex items-center mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Project
        </Link>

        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-muted rounded-lg">
                {pipelineIcons[job.pipeline_type]}
              </div>
              <div>
                <h1 className="text-2xl font-bold">{pipelineNames[job.pipeline_type]}</h1>
                <p className="text-sm text-muted-foreground">Job {job.id}</p>
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            {canSubmit && (
              <Button
                onClick={() => submitMutation.mutate()}
                disabled={submitMutation.isPending || isUploading}
              >
                {(submitMutation.isPending || isUploading) ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                )}
                {isUploading ? (
                  uploadProgress
                    ? `Uploading ${uploadProgress.current}/${uploadProgress.total}...`
                    : 'Uploading...'
                ) : 'Submit Job'}
              </Button>
            )}
            {canCancel && (
              <Button
                variant="outline"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
              >
                <XCircle className="mr-2 h-4 w-4" />
                Cancel
              </Button>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2 space-y-6">
          {/* Status Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Status
                <span className={`text-white text-xs px-2 py-1 rounded-full ${stateColors[job.state]}`}>
                  {job.state.replace('_', ' ')}
                </span>
              </CardTitle>
              <CardDescription>{stateDescriptions[job.state]}</CardDescription>
            </CardHeader>
            <CardContent>
              {isProcessing && (
                <div className="flex items-center gap-2 text-blue-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Processing...</span>
                </div>
              )}
              {isCompleted && job.state === 'SUCCEEDED' && (
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle className="h-4 w-4" />
                  <span>Job completed successfully! You can download the results below.</span>
                </div>
              )}
              {job.hold_reason && (
                <div className="flex items-center gap-2 text-orange-600">
                  <AlertCircle className="h-4 w-4" />
                  <span>{job.hold_reason}</span>
                </div>
              )}
              {job.error_message && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">{job.error_message}</p>
                  {job.error_code && (
                    <p className="text-xs text-red-500 mt-1">Code: {job.error_code}</p>
                  )}
                </div>
              )}
              {submitError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg mt-2">
                  <p className="text-sm text-red-700">Submit Error: {submitError}</p>
                </div>
              )}
              {uploadError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg mt-2">
                  <p className="text-sm text-red-700">Upload Error: {uploadError}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Upload Section for Draft Jobs */}
          {job.state === 'DRAFT' && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="h-5 w-5" />
                  Upload Files
                </CardTitle>
                <CardDescription>
                  Upload an image to convert to a 3D relief model.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileSelect}
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  multiple={job.pipeline_type === 'SCAN'} // Enable multiple for SCAN
                  aria-label="Select image file"
                />

                {selectedFiles.length === 0 ? (
                  <div
                    className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-8 text-center cursor-pointer hover:border-muted-foreground/50 transition-colors"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-4" />
                    <p className="text-sm text-muted-foreground mb-2">
                      Drag and drop your image{job.pipeline_type === 'SCAN' ? 's' : ''} here, or click to browse
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {job.pipeline_type === 'SCAN'
                        ? 'Recommended: 30+ photos for best results'
                        : 'Supported formats: JPG, PNG, WebP (max 100MB)'}
                    </p>
                    <Button variant="outline" className="mt-4" type="button">
                      Select File{job.pipeline_type === 'SCAN' ? 's' : ''}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Validation Warning for SCAN */}
                    {job.pipeline_type === 'SCAN' && selectedFiles.length < 2 && (
                      <div className="flex items-center gap-2 p-3 bg-red-100 text-red-700 rounded-lg text-sm">
                        <AlertCircle className="h-4 w-4" />
                        <span>At least 2 photos are required for photogrammetry.</span>
                      </div>
                    )}
                    {job.pipeline_type === 'SCAN' && selectedFiles.length >= 2 && selectedFiles.length < 30 && (
                      <div className="flex items-center gap-2 p-3 bg-yellow-100 text-yellow-700 rounded-lg text-sm">
                        <AlertCircle className="h-4 w-4" />
                        <span>Recommended: 30+ photos for high detail (Selected: {selectedFiles.length}).</span>
                      </div>
                    )}

                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">{selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''} selected</span>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={clearAllFiles}>Clear All</Button>
                        <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>Add More</Button>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-h-96 overflow-y-auto pr-2">
                      {selectedFiles.map((file, index) => (
                        <div key={index} className="relative border rounded-lg overflow-hidden group">
                          {filePreviews[index] && (
                            <img
                              src={filePreviews[index]}
                              alt="Preview"
                              className="w-full h-32 object-cover bg-muted"
                            />
                          )}
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                            <button
                              onClick={() => handleRemoveFile(index)}
                              className="p-1 bg-red-500 rounded-full text-white hover:bg-red-600"
                              title="Remove"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>
                          <div className="p-2 text-xs truncate bg-background/90 absolute bottom-0 w-full">
                            {file.name}
                          </div>
                        </div>
                      ))}
                    </div>

                    <p className="text-sm text-muted-foreground text-center">
                      Click &quot;Submit Job&quot; above to start processing.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* 3D Preview for STL artifacts */}
          {artifacts && (() => {
            const stlArtifact = artifacts.find(a => a.format === 'stl')
            if (!stlArtifact) return null
            return (
              <Card>
                <CardHeader>
                  <CardTitle>3D Preview</CardTitle>
                  <CardDescription>
                    Interactive preview of the generated model
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80 rounded-lg overflow-hidden">
                    <STLViewer
                      modelUrl={api.uploads.getDownloadUrl(stlArtifact.id)}
                      className="h-full"
                    />
                  </div>
                </CardContent>
              </Card>
            )
          })()}

          {/* Artifacts Section */}
          {artifacts && artifacts.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Output Artifacts</CardTitle>
                <CardDescription>
                  Files generated by this job
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {artifacts.map((artifact) => (
                    <div
                      key={artifact.id}
                      className="flex items-center justify-between p-3 bg-muted rounded-lg"
                    >
                      <div>
                        <p className="font-medium">{artifact.label || artifact.artifact_type}</p>
                        <p className="text-sm text-muted-foreground">
                          {artifact.format.toUpperCase()} • {(artifact.size_bytes / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                      <a
                        href={api.uploads.getDownloadUrl(artifact.id)}
                        download
                      >
                        <Button variant="outline" size="sm">
                          <Download className="h-4 w-4 mr-2" />
                          Download
                        </Button>
                      </a>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quality Score */}
          {job.quality_score !== undefined && job.quality_score !== null && (
            <Card>
              <CardHeader>
                <CardTitle>Quality Score</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center">
                  <div className={`text-4xl font-bold ${job.quality_score >= 0.8 ? 'text-green-500' :
                      job.quality_score >= 0.6 ? 'text-yellow-500' : 'text-red-500'
                    }`}>
                    {(job.quality_score * 100).toFixed(0)}%
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {job.quality_score >= 0.8 ? 'Great' :
                      job.quality_score >= 0.6 ? 'Good' : 'Needs Improvement'}
                  </p>
                </div>
                {job.quality_summary && (
                  <div className="mt-4 space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Input Quality</span>
                      <span>{(job.quality_summary.input_quality * 100).toFixed(0)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Reconstruction</span>
                      <span>{(job.quality_summary.reconstruction_confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Printability</span>
                      <span>{((1 - job.quality_summary.printability_risk) * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Job Details */}
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span>{formatDateTime(job.created_at)}</span>
              </div>
              {job.submitted_at && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Submitted</span>
                  <span>{formatDateTime(job.submitted_at)}</span>
                </div>
              )}
              {job.completed_at && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Completed</span>
                  <span>{formatDateTime(job.completed_at)}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Printer Profile</span>
                <span className="truncate ml-2">{job.printer_profile_id}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
