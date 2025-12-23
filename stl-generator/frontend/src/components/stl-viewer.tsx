'use client'

import { useState, useEffect, Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, PerspectiveCamera, Grid, Environment } from '@react-three/drei'
import * as THREE from 'three'
import { STLLoader } from 'three/addons/loaders/STLLoader.js'

interface ModelProps {
  url: string
}

function STLModel({ url }: ModelProps) {
  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null)
  const [error, setError] = useState<string | null>(null)
  
  useEffect(() => {
    if (!url) return
    
    const loader = new STLLoader()
    loader.load(
      url,
      (loadedGeometry) => {
        // Center the geometry
        loadedGeometry.center()
        loadedGeometry.computeBoundingBox()
        
        // Scale to fit
        const box = loadedGeometry.boundingBox
        if (box) {
          const size = new THREE.Vector3()
          box.getSize(size)
          const maxDim = Math.max(size.x, size.y, size.z)
          const scale = 10 / maxDim
          loadedGeometry.scale(scale, scale, scale)
        }
        setGeometry(loadedGeometry)
        setError(null)
      },
      undefined,
      (err) => {
        console.error('STL load error:', err)
        setError('Failed to load 3D model')
      }
    )
  }, [url])
  
  if (error) {
    return null
  }
  
  if (!geometry) {
    return null
  }
  
  return (
    <mesh geometry={geometry}>
      <meshPhongMaterial 
        color={0x888888}
        specular={0x111111}
        shininess={200}
      />
    </mesh>
  )
}

interface STLViewerProps {
  modelUrl: string
  className?: string
}

export function STLViewer({ modelUrl, className = '' }: STLViewerProps) {
  return (
    <div className={`w-full h-full bg-gray-100 rounded-lg ${className}`}>
      <Canvas>
        <PerspectiveCamera makeDefault position={[15, 15, 15]} />
        <OrbitControls 
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
        />
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <Suspense fallback={null}>
          <STLModel url={modelUrl} />
        </Suspense>
        <Grid 
          args={[20, 20]} 
          cellSize={1} 
          cellThickness={0.5} 
          cellColor={'#6b7280'} 
          sectionSize={5} 
          sectionThickness={1}
          sectionColor={'#374151'}
          fadeDistance={30}
          fadeStrength={1}
          followCamera={false}
        />
        <Environment preset="studio" />
      </Canvas>
    </div>
  )
}
