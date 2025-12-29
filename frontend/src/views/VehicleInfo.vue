<script setup lang="ts">
import { ref } from 'vue'
import EntityCardBoard from '@/components/EntityCardBoard.vue'
import type { Vehicle } from '@/types'
import { VehicleCardColumns, VehicleEditColumns } from '@/types'
import { apiFetch, apiJson } from '@/services/api'

// 状态变量
const vehicles = ref<Vehicle[]>([])
const total = ref(0)
const vehicle_regex = /^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-HJ-NP-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂港澳]$/

// 数据操作函数
async function searchVehicles(query: string, limit: number, offset: number) {
    const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) })
    const data = await apiJson<{ data?: Vehicle[]; total?: number }>(`/api/vehicles?${params}`)
    vehicles.value = data.data ?? []
    total.value = data.total ?? vehicles.value.length
}

async function createVehicle(vehicle: Partial<Vehicle>) {
    if (!vehicle.vehicle_id || !vehicle_regex.test(vehicle.vehicle_id)) {
        throw new Error(`无效的车牌号格式: ${vehicle.vehicle_id}。示例: 京A12345、沪B6789挂`)
    }
    const res = await apiFetch('/api/vehicles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(vehicle),
    })
    if (!res.ok) throw new Error('添加车辆信息失败')
}

async function updateVehicle(vehicleId: Vehicle['vehicle_id'], updates: Partial<Vehicle>) {
    if (updates.vehicle_id && !vehicle_regex.test(updates.vehicle_id)) {
        throw new Error(`无效的车牌号格式: ${updates.vehicle_id}。示例: 京A12345、沪B6789挂`)
    }
    const res = await apiFetch(`/api/vehicles/${encodeURIComponent(String(vehicleId))}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
    })
    if (!res.ok) throw new Error('更新失败')
}

async function deleteVehicle(vehicleId: Vehicle['vehicle_id']) {
    const res = await apiFetch(`/api/vehicles/${encodeURIComponent(String(vehicleId))}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除失败')
}

// EntityCardBoard 操作接口
const vehicleOps = {
    get data() { return vehicles.value },
    get total() { return total.value },
    search: searchVehicles,
    create: async (item: Partial<Vehicle>) => {
        return createVehicle(item)
    },
    update: async (id: Vehicle['vehicle_id'], updates: Partial<Vehicle>) => {
        return updateVehicle(id, updates)
    },
    delete: deleteVehicle,
}
</script>

<template>
    <div class="p-6">
        <h2 class="text-xl font-bold mb-4">车辆管理</h2>

        <EntityCardBoard :operations="vehicleOps" :columns="VehicleCardColumns" :createColumns="VehicleEditColumns"
            :editColumns="VehicleEditColumns" titleKey="vehicle_id" :gridColumns="4" />
    </div>
</template>