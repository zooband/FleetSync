<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import EntityCardBoard from '@/components/EntityCardBoard.vue'
import type { DistributionCenter } from '@/types'
import { DistributionCenterColumns } from '@/types'
import { apiFetch, apiJson } from '@/services/api'

const router = useRouter()

const centers = ref<DistributionCenter[]>([])
const total = ref(0)

async function searchCenters(query: string, limit: number, offset: number) {
    const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) })
    const data = await apiJson<{ data: DistributionCenter[]; total: number }>(`/api/distribution-centers?${params}`)
    centers.value = data.data
    total.value = data.total
}

async function createDistributionCenter(item: Partial<DistributionCenter>) {
    const res = await apiFetch('/api/distribution-centers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item),
    })
    if (!res.ok) throw new Error('创建配送中心失败')
}

async function updateDistributionCenter(id: number, updates: Partial<DistributionCenter>) {
    const res = await apiFetch(`/api/distribution-centers/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
    })
    if (!res.ok) throw new Error('更新配送中心失败')
}

async function deleteDistributionCenter(id: number) {
    const res = await apiFetch(`/api/distribution-centers/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除配送中心失败')
}

function goToDistributionCenter(center: DistributionCenter) {
    router.push({ path: `/distribution/${center.center_id}` })
}

const centerOps = {
    get data() {
        return centers.value
    },
    get total() {
        return total.value
    },
    search: searchCenters,
    create: createDistributionCenter,
    update: updateDistributionCenter,
    delete: deleteDistributionCenter,
}
</script>

<template>
    <div class="p-6">
        <h2 class="text-xl font-bold mb-4">配送中心</h2>

        <EntityCardBoard :operations="centerOps" :columns="DistributionCenterColumns" titleKey="center_name"
            :click="goToDistributionCenter" :gridColumns="4" />
    </div>
</template>
