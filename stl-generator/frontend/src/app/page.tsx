'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Plus, Folder, Upload, Sparkles } from 'lucide-react'
import { ProjectList } from '@/components/project-list'
import { CreateProjectDialog } from '@/components/create-project-dialog'

export default function Home() {
  const [createProjectOpen, setCreateProjectOpen] = useState(false)

  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold mb-2">3D STL Generator</h1>
          <p className="text-muted-foreground">
            Transform images into 3D-printable STL files
          </p>
        </div>
        <Button onClick={() => setCreateProjectOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      <Tabs defaultValue="projects" className="space-y-4">
        <TabsList>
          <TabsTrigger value="projects">
            <Folder className="mr-2 h-4 w-4" />
            Projects
          </TabsTrigger>
          <TabsTrigger value="pipelines">
            <Sparkles className="mr-2 h-4 w-4" />
            Pipelines
          </TabsTrigger>
        </TabsList>

        <TabsContent value="projects" className="space-y-4">
          <ProjectList />
        </TabsContent>

        <TabsContent value="pipelines" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Relief Pipeline</CardTitle>
                <CardDescription>
                  Single image to relief/bas-relief STL
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm mb-4">
                  Convert a single image into a 3D relief suitable for printing
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center">
                    <div className="w-2 h-2 bg-green-500 rounded-full mr-2" />
                    <span>Available (MVP)</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="opacity-60">
              <CardHeader>
                <CardTitle>Multi-Photo Scan</CardTitle>
                <CardDescription>
                  Photogrammetry from multiple photos
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm mb-4">
                  Create 3D models from 30-200 photos using photogrammetry
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center">
                    <div className="w-2 h-2 bg-yellow-500 rounded-full mr-2" />
                    <span>Coming in v1</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="opacity-60">
              <CardHeader>
                <CardTitle>Generative Minis</CardTitle>
                <CardDescription>
                  AI-generated miniatures from text
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm mb-4">
                  Generate grimdark sci-fi miniatures from text prompts
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center">
                    <div className="w-2 h-2 bg-gray-500 rounded-full mr-2" />
                    <span>Coming in v2</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <CreateProjectDialog
        open={createProjectOpen}
        onOpenChange={setCreateProjectOpen}
      />
    </div>
  )
}
