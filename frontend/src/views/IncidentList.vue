<script setup lang="ts">
import { ref } from 'vue'
import DBtable from '@/components/DBtable.vue'
import type { Incident } from '@/types'
import { IncidentColumns } from '@/types'
import { apiFetch, apiJson } from '@/services/api'

// 状态变量
const incidents = ref<Incident[]>([])
const total = ref(0)
const loading = ref(false)

// 数据操作函数
async function searchIncidents(query: string, limit: number, offset: number) {
    loading.value = true
    try {
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

async function createIncident(incident: Partial<Incident>) {
    const res = await apiFetch('/api/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(incident),
    })
    if (!res.ok) throw new Error('添加异常事件失败')
}

async function updateIncident(id: number, updates: Partial<Incident>) {
    const res = await apiFetch(`/api/incidents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
    })
    if (!res.ok) throw new Error('更新异常事件失败')
}

async function deleteIncident(id: number) {
    const res = await apiFetch(`/api/incidents/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除异常事件失败')
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

        <DBtable :operations="incidentOps" :columns="IncidentColumns" />
    </div>
</template>