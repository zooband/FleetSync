<script setup lang="ts">
import { ref } from 'vue'
import DBtable from '@/components/DBtable.vue'
import type { Driver } from '@/types'
import { DriverColumns } from '@/types'

// 状态变量
const drivers = ref<Driver[]>([])
const total = ref(0)
const loading = ref(false)

// 数据操作函数
async function searchDrivers(query: string, limit: number, offset: number) {
    loading.value = true
    try {
        const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) })
        const res = await fetch(`http://localhost:8000/drivers?${params}`)
        if (!res.ok) throw new Error('加载失败')
        const data = await res.json()
        drivers.value = data.data
        total.value = data.total
    } catch (err) {
        throw err
    } finally {
        loading.value = false
    }
}

async function createDriver(driver: Partial<Driver>) {
    const missing = DriverColumns
        .filter(col => col.editable && col.required !== false)
        .filter(col => {
            const v = (driver as Record<string, unknown>)[col.key]
            if (col.type === 'number') return v == null || (typeof v === 'number' && Number.isNaN(v))
            const s = v == null ? '' : String(v)
            return s.trim().length === 0
        })
        .map(col => col.label)

    if (missing.length > 0) {
        throw new Error(`请填写必填项：${missing.join('、')}`)
    }

    const res = await fetch('http://localhost:8000/drivers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(driver),
    })
    if (!res.ok) throw new Error('创建失败')
}

async function updateDriver(id: number, updates: Partial<Driver>) {
    const missing = DriverColumns
        .filter(col => col.editable && col.required !== false)
        .filter(col => {
            if (!(col.key in updates)) return false
            const v = (updates as Record<string, unknown>)[col.key]
            if (col.type === 'number') return v == null || (typeof v === 'number' && Number.isNaN(v))
            const s = v == null ? '' : String(v)
            return s.trim().length === 0
        })
        .map(col => col.label)
    if (missing.length > 0) {
        throw new Error(`请填写必填项：${missing.join('、')}`)
    }
    const res = await fetch(`http://localhost:8000/drivers/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
    })
    if (!res.ok) throw new Error('更新失败')
}

async function deleteDriver(id: number) {
    const res = await fetch(`http://localhost:8000/drivers/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除失败')
}

// DBtable 操作接口
const driverOps = {
    get data() { return drivers.value },
    get total() { return total.value },
    search: searchDrivers,
    create: async (item: Partial<Driver>) => {
        return createDriver(item)
    },
    update: async (id: number, updates: Partial<Driver>) => {
        return updateDriver(id, updates)
    },
    delete: deleteDriver,
}

// 初始加载
searchDrivers('', 10, 0)
</script>

<template>
    <div class="p-6">
        <h2 class="text-xl font-bold mb-4">司机管理</h2>

        <DBtable :operations="driverOps" :columns="DriverColumns" />
    </div>
</template>