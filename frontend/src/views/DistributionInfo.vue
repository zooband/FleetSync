<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import EntityCardBoard from '@/components/EntityCardBoard.vue'
import CardGrid from '@/components/CardGrid.vue'
import EntityCard from '@/components/EntityCard.vue'
import type { Columns, Fleet } from '@/types'
import { FleetColumns } from '@/types'
import { apiFetch, apiJson } from '@/services/api'
import { auth } from '@/services/auth'
import { useToast } from 'primevue/usetoast'
import PrimeButton from 'primevue/button'
import PrimeDialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

const route = useRoute()

const centerId = computed(() => {
    const raw = route.params.centerId
    const n = typeof raw === 'string' ? Number(raw) : Array.isArray(raw) ? Number(raw[0]) : Number(raw)
    return Number.isFinite(n) ? n : NaN
})

const isAdmin = computed(() => auth.value?.role === 'admin')

type CenterDetail = { center_id: number; center_name: string }
const centerDetail = ref<CenterDetail | null>(null)
const centerEditVisible = ref(false)
const centerEditSubmitting = ref(false)
const editCenterName = ref('')
const toast = useToast()

async function fetchCenterDetail() {
    if (!Number.isFinite(centerId.value)) return
    centerDetail.value = await apiJson<CenterDetail>(`/api/distribution-centers/${centerId.value}`)
}

function openCenterEdit() {
    if (!isAdmin.value) return
    editCenterName.value = String(centerDetail.value?.center_name ?? '').trim()
    centerEditVisible.value = true
}

async function confirmCenterEdit() {
    if (!Number.isFinite(centerId.value)) throw new Error('无效的配送中心ID')
    const payload = { center_name: editCenterName.value.trim() }
    if (!payload.center_name) throw new Error('请填写配送中心名称')

    centerEditSubmitting.value = true
    try {
        const res = await apiFetch(`/api/distribution-centers/${centerId.value}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        if (!res.ok) {
            const msg = await res.text().catch(() => '')
            throw new Error(msg || '更新配送中心失败')
        }
        centerEditVisible.value = false
        await fetchCenterDetail()
        toast.add({ severity: 'success', summary: '成功', detail: '配送中心信息已更新', life: 1500 })
    } catch (e) {
        toast.add({ severity: 'error', summary: '错误', detail: (e as Error).message || '操作失败' })
        throw e
    } finally {
        centerEditSubmitting.value = false
    }
}

type PaginatedResponse<T> = {
    data: T[]
    total: number
}

const fleets = ref<Fleet[]>([])
const total = ref(0)

type CenterAvailableVehicle = {
    vehicle_id: string
    remaining_weight: number
    remaining_volume: number
}

type CenterUnavailableVehicle = {
    vehicle_id: string
    status: string
}

type CenterVehicleResources = {
    available: CenterAvailableVehicle[]
    unavailable: CenterUnavailableVehicle[]
}

const availableVehicles = ref<CenterAvailableVehicle[]>([])
const unavailableVehicles = ref<CenterUnavailableVehicle[]>([])
const vehicleResourcesLoading = ref(false)
const vehicleTab = ref<'available' | 'unavailable'>('available')

async function fetchCenterVehicleResources() {
    if (!Number.isFinite(centerId.value)) return
    vehicleResourcesLoading.value = true
    try {
        const data = await apiJson<CenterVehicleResources>(
            `/api/distribution-centers/${centerId.value}/vehicle-resources`
        )
        availableVehicles.value = data.available ?? []
        unavailableVehicles.value = data.unavailable ?? []
    } finally {
        vehicleResourcesLoading.value = false
    }
}

async function searchCenterFleets(query: string, limit: number, offset: number) {
    if (!Number.isFinite(centerId.value)) throw new Error('无效的配送中心ID')

    const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) })
    const data = await apiJson<PaginatedResponse<Fleet>>(`/api/distribution-centers/${centerId.value}/fleets?${params}`)
    fleets.value = data.data
    total.value = data.total
}

async function createCenterFleet(item: Partial<Fleet>) {
    if (!Number.isFinite(centerId.value)) throw new Error('无效的配送中心ID')

    const res = await apiFetch(`/api/distribution-centers/${centerId.value}/fleets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // 后端已改为：创建车队时直接提交主管信息
        body: JSON.stringify(item),
    })

    if (!res.ok) throw new Error('创建车队失败')
}

async function updateCenterFleet(fleet_id: Fleet['fleet_id'], updates: Partial<Fleet>) {
    if (!Number.isFinite(centerId.value)) throw new Error('无效的配送中心ID')

    const payload: Partial<Fleet> = {}
    if (updates.fleet_name != null) payload.fleet_name = updates.fleet_name

    const res = await apiFetch(
        `/api/distribution-centers/${centerId.value}/fleets/${encodeURIComponent(String(fleet_id))}`,
        {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        }
    )

    if (!res.ok) throw new Error('更新车队失败')
}

async function deleteCenterFleet(fleet_id: Fleet['fleet_id']) {
    if (!Number.isFinite(centerId.value)) throw new Error('无效的配送中心ID')

    const res = await apiFetch(
        `/api/distribution-centers/${centerId.value}/fleets/${encodeURIComponent(String(fleet_id))}`,
        { method: 'DELETE' }
    )

    if (!res.ok) throw new Error('删除车队失败')
}

const fleetOps = {
    get data() {
        return fleets.value
    },
    get total() {
        return total.value
    },
    search: searchCenterFleets,
    create: async (item: Partial<Fleet>) => {
        return createCenterFleet(item)
    },
    update: async (id: Fleet['fleet_id'], updates: Partial<Fleet>) => {
        return updateCenterFleet(id, updates)
    },
    delete: deleteCenterFleet,
}

const fleetCardColumns = FleetColumns.filter(c => c.key !== 'manager_id')

const createFleetColumns: readonly Columns[] = [
    { key: 'fleet_name', label: '车队名称', type: 'text', editable: true, isId: false, required: true },
    { key: 'manager_name', label: '调度主管姓名', type: 'text', editable: true, isId: false, required: true },
    { key: 'manager_contact', label: '调度主管联系方式', type: 'text', editable: true, isId: false, required: false },
]

const editFleetColumns: readonly Columns[] = [
    { key: 'fleet_name', label: '车队名称', type: 'text', editable: true, isId: false, required: true },
]

function goToFleet(fleet: Fleet) {
    if (!Number.isFinite(fleet.fleet_id)) return
    window.location.href = `#/fleet/${fleet.fleet_id}`
}

watch(
    () => centerId.value,
    () => {
        centerDetail.value = null
        fetchCenterDetail().catch(() => {
            centerDetail.value = null
        })
        fleets.value = []
        total.value = 0
        availableVehicles.value = []
        unavailableVehicles.value = []
        fetchCenterVehicleResources().catch(() => {
            availableVehicles.value = []
            unavailableVehicles.value = []
        })
    },
    { immediate: true }
)
</script>

<template>
    <div class="p-6 space-y-6">
        <div class="flex items-center justify-between mb-4">
            <h2 class="text-xl font-bold">配送中心详情</h2>
            <PrimeButton v-if="isAdmin" size="small" label="编辑" @click="openCenterEdit" />
        </div>

        <div class="grid grid-cols-2 gap-4 mb-6">
            <div class="flex flex-col">
                <span class="text-sm text-gray-500">配送中心ID</span>
                <span class="text-base">{{ Number.isFinite(centerId) ? centerId : '-' }}</span>
            </div>
            <div class="flex flex-col">
                <span class="text-sm text-gray-500">配送中心名</span>
                <span class="text-base">{{ centerDetail?.center_name ?? '-' }}</span>
            </div>
        </div>

        <h3 class="text-xl font-bold mb-4">下属车队</h3>
        <EntityCardBoard :key="`dc-${centerId}`" :operations="fleetOps" :columns="fleetCardColumns"
            :createColumns="createFleetColumns" :editColumns="editFleetColumns" titleKey="fleet_name" :click="goToFleet"
            :gridColumns="4" />

        <!-- 车队资源查询：车辆负载情况 -->
        <div class="mt-8 space-y-4">
            <h3 class="text-xl font-bold">车队资源查询</h3>

            <Tabs v-model:value="vehicleTab">
                <TabList>
                    <Tab value="available">可用车辆</Tab>
                    <Tab value="unavailable">不可用车辆</Tab>
                </TabList>

                <TabPanels>
                    <TabPanel value="available">
                        <DataTable :value="availableVehicles" :loading="vehicleResourcesLoading" removableSort>
                            <Column field="vehicle_id" header="车牌号" sortable />
                            <Column field="remaining_weight" header="剩余载重" sortable />
                            <Column field="remaining_volume" header="剩余容积" sortable />
                        </DataTable>
                    </TabPanel>

                    <TabPanel value="unavailable">
                        <div v-if="unavailableVehicles.length === 0" class="text-sm text-gray-500">暂无不可用车辆</div>
                        <CardGrid v-else :columns="4">
                            <EntityCard v-for="v in unavailableVehicles" :key="v.vehicle_id" :title="v.vehicle_id"
                                :subtitle="v.status" :clickable="false" :allowEdit="false" :allowDelete="false" />
                        </CardGrid>
                    </TabPanel>
                </TabPanels>
            </Tabs>
        </div>

        <PrimeDialog v-model:visible="centerEditVisible" modal header="编辑配送中心信息" :style="{ width: '32rem' }">
            <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">配送中心名称*</label>
                <InputText v-model="editCenterName" />
            </div>
            <template #footer>
                <PrimeButton label="取消" severity="secondary" @click="centerEditVisible = false" />
                <PrimeButton label="确认" :loading="centerEditSubmitting" @click="confirmCenterEdit" />
            </template>
        </PrimeDialog>
    </div>
</template>
