'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ImageIcon, Camera, Sparkles, Check } from 'lucide-react'
import { api, Job } from '@/lib/api'

interface CreateJobDialogProps {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

type PipelineType = Job['pipeline_type']

const pipelines: Array<{
  type: PipelineType
  name: string
  description: string
  icon: React.ReactNode
  available: boolean
}> = [
  {
    type: 'RELIEF',
    name: 'Relief Pipeline',
    description: 'Convert a single image into a 3D relief suitable for printing',
    icon: <ImageIcon className="h-8 w-8" />,
    available: true,
  },
  {
    type: 'SCAN',
    name: 'Multi-Photo Scan',
    description: 'Create 3D models from 30-200 photos using photogrammetry',
    icon: <Camera className="h-8 w-8" />,
    available: false,
  },
  {
    type: 'GENERATIVE',
    name: 'Generative Minis',
    description: 'Generate grimdark sci-fi miniatures from text prompts',
    icon: <Sparkles className="h-8 w-8" />,
    available: false,
  },
]

export function CreateJobDialog({ projectId, open, onOpenChange }: CreateJobDialogProps) {
  const [selectedPipeline, setSelectedPipeline] = useState<PipelineType | null>(null)
  const queryClient = useQueryClient()

  const createJobMutation = useMutation({
    mutationFn: async (pipelineType: PipelineType) => {
      return api.jobs.create(projectId, {
        pipeline_type: pipelineType,
        printer_profile_id: 'pp_default_fdm',
        config: {},
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs', projectId] })
      onOpenChange(false)
      setSelectedPipeline(null)
    },
  })

  const handleCreate = () => {
    if (selectedPipeline) {
      createJobMutation.mutate(selectedPipeline)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Create New Job</DialogTitle>
          <DialogDescription>
            Select a pipeline to process your images into 3D models.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {pipelines.map((pipeline) => (
            <Card
              key={pipeline.type}
              className={`cursor-pointer transition-all ${
                !pipeline.available ? 'opacity-50 cursor-not-allowed' : ''
              } ${
                selectedPipeline === pipeline.type
                  ? 'ring-2 ring-primary'
                  : 'hover:shadow-md'
              }`}
              onClick={() => {
                if (pipeline.available) {
                  setSelectedPipeline(pipeline.type)
                }
              }}
            >
              <CardHeader className="flex flex-row items-center gap-4 pb-2">
                <div className={`p-2 rounded-lg ${
                  selectedPipeline === pipeline.type 
                    ? 'bg-primary text-primary-foreground' 
                    : 'bg-muted'
                }`}>
                  {pipeline.icon}
                </div>
                <div className="flex-1">
                  <CardTitle className="text-lg flex items-center gap-2">
                    {pipeline.name}
                    {selectedPipeline === pipeline.type && (
                      <Check className="h-4 w-4 text-primary" />
                    )}
                  </CardTitle>
                  <CardDescription>{pipeline.description}</CardDescription>
                </div>
                {!pipeline.available && (
                  <span className="text-xs bg-muted px-2 py-1 rounded">
                    Coming Soon
                  </span>
                )}
              </CardHeader>
            </Card>
          ))}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!selectedPipeline || createJobMutation.isPending}
          >
            {createJobMutation.isPending ? 'Creating...' : 'Create Job'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
