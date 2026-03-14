import client from './client'
import type { MaterialInfo, StackLayer } from '../types'

export async function getMaterials(): Promise<MaterialInfo[]> {
  const { data } = await client.get('/materials/')
  return data
}

export async function uploadPstar(
  name: string,
  density: number,
  file: File,
  replace = false
): Promise<MaterialInfo> {
  const form = new FormData()
  form.append('name', name)
  form.append('density', String(density))
  form.append('replace', String(replace))
  form.append('file', file)
  const { data } = await client.post('/materials/upload-pstar', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function batchLoadMaterials(): Promise<{ loaded: number }> {
  const { data } = await client.post('/materials/batch-load')
  return data
}

export async function validateStack(layers: StackLayer[]) {
  const { data } = await client.post('/stack/validate', layers)
  return data
}

export async function exportStackJson(layers: StackLayer[]) {
  const { data } = await client.post('/stack/export-json', layers)
  return data
}

export async function importStackJson(file: File): Promise<{ layers: StackLayer[] }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post('/stack/import-json', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
