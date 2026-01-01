<script setup lang="ts">
import { ref } from 'vue'
import DBtable from '@/components/DBtable.vue'
import type { Incident } from '@/types'
import { IncidentColumns } from '@/types'
import { apiFetch, apiJson } from '@/services/api'

// 统一读取后端错误消息（优先显示 detail/message 字段）
async function readBackendError(res: Response): Promise<string> {
    const msg = `请求失败 (${res.status})`
    try {
        const text = await res.text()
        const trimmed = text.trim()
        if (!trimmed) return msg

        try {
            const raw = JSON.parse(trimmed) as { detail?: unknown; message?: unknown }
            const detail = raw?.detail ?? raw?.message
            if (typeof detail === 'string' && detail.trim()) return detail.trim()
        } catch {
            // 非 JSON，直接返回文本
        }

        return trimmed
    } catch {
        return msg
    }
}

// 状态变量
const incidents = ref<Incident[]>([])
const total = ref(0)
const loading = ref(false)

// 记录最近一次查询分页参数，便于自定义操作后刷新当前页
const lastQuery = ref('')
const lastLimit = ref(10)
const lastOffset = ref(0)

// 数据操作函数
async function searchIncidents(query: string, limit: number, offset: number) {
    loading.value = true
    try {
        lastQuery.value = query
        lastLimit.value = limit
        lastOffset.value = offset
        const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) })
        const data = await apiJson<{ data: Incident[]; total: number }>(`/api/incidents?${params}`)
        incidents.value = data.data
        total.value = data.total
    } catch (err) {
        throw err
    } finally {
        loading.value = false
    }
}

async function refreshIncidents() {
    await searchIncidents(lastQuery.value, lastLimit.value, lastOffset.value)
}

async function createIncident(incident: Partial<Incident>) {
    const res = await apiFetch('/api/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // 后端会自动推导司机/时间/类型/处理状态，这里只提交 vehicle_id
        body: JSON.stringify({
            vehicle_id: (incident as any)?.vehicle_id,
            incident_description: (incident as any)?.incident_description,
            fine_amount: (incident as any)?.fine_amount,
        }),
    })
    if (!res.ok) throw new Error(await readBackendError(res))
}

async function updateIncident(id: number, updates: Partial<Incident>) {
    const res = await apiFetch(`/api/incidents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
    })
    if (!res.ok) throw new Error(await readBackendError(res))
}

async function deleteIncident(id: number) {
    const res = await apiFetch(`/api/incidents/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(await readBackendError(res))
}

async function markIncidentHandled(row: Incident) {
    const incidentId = Number((row as any)?.incident_id)
    if (!Number.isFinite(incidentId)) throw new Error('缺少 incident_id，无法更新')
    await updateIncident(incidentId, { handle_status: '已处理' } as any)
    await refreshIncidents()
}

// DBtable 操作接口
const incidentOps = {
    get data() { return incidents.value },
    get total() { return total.value },
    search: searchIncidents,
    create: async (item: Partial<Incident>) => {
        return createIncident(item)
    },
    update: async (id: number, updates: Partial<Incident>) => {
        return updateIncident(id, updates)
    },
    delete: deleteIncident,
}

// 初始加载
searchIncidents('', 10, 0)
</script>

<template>
    <div class="p-6">
        <h2 class="text-xl font-bold mb-4">异常事件</h2>

        <DBtable :operations="incidentOps" :columns="IncidentColumns" :allowEdit="false">
            <template #row-actions="{ data }">
                <button
                    class="p-button p-component p-button-sm"
                    :disabled="String((data as any)?.handle_status || '') === '已处理'"
                    @click="markIncidentHandled(data as any)"
                >
                    标记为已处理
                </button>
            </template>
        </DBtable>
    </div>
</template>