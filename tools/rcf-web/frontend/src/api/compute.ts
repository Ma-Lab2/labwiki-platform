import client from './client'
import type {
  AsyncTaskResponse,
  EnergyScanRequest,
  EnergyScanResponse,
  LinearDesignRequest,
  LinearDesignResponse,
} from '../types'

export async function energyScan(req: EnergyScanRequest): Promise<EnergyScanResponse> {
  const { data } = await client.post('/compute/energy-scan', req)
  return data
}

export async function energyScanAsync(req: EnergyScanRequest): Promise<AsyncTaskResponse> {
  const { data } = await client.post('/compute/energy-scan/async', req)
  return data
}

export async function linearDesign(req: LinearDesignRequest): Promise<LinearDesignResponse> {
  const { data } = await client.post('/compute/linear-design', req)
  return data
}

export async function linearDesignAsync(req: LinearDesignRequest): Promise<AsyncTaskResponse> {
  const { data } = await client.post('/compute/linear-design/async', req)
  return data
}
