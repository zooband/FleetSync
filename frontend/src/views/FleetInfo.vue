<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EntityCardBoard from '@/components/EntityCardBoard.vue'
import type { Columns, Driver, Vehicle } from '@/types'
import { DriverColumns, VehicleColumns, VehicleEditColumns } from '@/types'
import DatePicker from 'primevue/datepicker'
import PrimeButton from 'primevue/button'
import PrimeDialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import AutoComplete from 'primevue/autocomplete'
import { useToast } from 'primevue/usetoast'
import { apiFetch, apiJson } from '@/services/api'
import { auth } from '@/services/auth'

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
            // ignore
        }

        return trimmed
    } catch {
        return msg
    }
}

async function apiOk(input: string, init: RequestInit = {}): Promise<Response> {
    const res = await apiFetch(input, init)
    if (!res.ok) throw new Error(await readBackendError(res))
    return res
}

function normalizeDriverPid(raw: unknown): string {
    const s = String(raw ?? '').trim()
    if (!s) return ''
    if (/^D\d+$/i.test(s)) return `D${s.slice(1)}`
    if (/^\d+$/.test(s)) return `D${s}`
    return s
}

const route = useRoute()
const router = useRouter()

const fleetId = computed(() => {
    const raw = route.params.fleetId
    const n = typeof raw === 'string' ? Number(raw) : Array.isArray(raw) ? Number(raw[0]) : Number(raw)
    return Number.isFinite(n) ? n : NaN
})

type PaginatedResponse<T> = {
    data: T[]
    total: number
}

type FleetDetail = {
    fleet_id: number
    fleet_name: string
    manager_id: number
    manager_name: string
    manager_contact: string | null
    center_id: number
}

// 车队车辆列表的后端返回会附带额外字段（不在全局 Vehicle 类型里）
type FleetVehicle = Vehicle & {
    driver_id: number | null
}

type VehicleLocalPatch = Partial<FleetVehicle> & { vehicle_id?: never }
type DriverLocalPatch = Partial<Driver> & { person_id?: never }

const fleetDetail = ref<FleetDetail | null>(null)

const vehicles = ref<FleetVehicle[]>([])
const vehicle_total = ref(0)

const drivers = ref<Driver[]>([])
const driver_total = ref(0)

const toast = useToast()

const isManagerReadonly = computed(() => auth.value?.role === 'manager')
const isAdmin = computed(() => auth.value?.role === 'admin')
const isOperator = computed(() => auth.value?.role === 'admin' || auth.value?.role === 'manager')

// 车队信息编辑（仅 admin）
const fleetEditVisible = ref(false)
const fleetEditSubmitting = ref(false)
const editFleetName = ref('')
const editManagerName = ref('')
const editManagerContact = ref('')

function openFleetEdit() {
    if (!isAdmin.value) return
    editFleetName.value = String(fleetDetail.value?.fleet_name ?? '').trim()
    editManagerName.value = String(fleetDetail.value?.manager_name ?? '').trim()
    editManagerContact.value = String(fleetDetail.value?.manager_contact ?? '')
    fleetEditVisible.value = true
}

async function confirmFleetEdit() {
    if (!Number.isFinite(fleetId.value)) throw new Error('无效的车队ID')
    const payload = {
        fleet_name: editFleetName.value.trim(),
        manager_name: editManagerName.value.trim(),
        manager_contact: editManagerContact.value.trim() ? editManagerContact.value.trim() : null,
    }
    if (!payload.fleet_name) throw new Error('请填写车队名')
    if (!payload.manager_name) throw new Error('请填写调度主管姓名')

    fleetEditSubmitting.value = true
    try {
        await apiOk(`/api/fleets/${fleetId.value}/manager/${fleetDetail.value?.manager_id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        fleetEditVisible.value = false
        await fetchFleetDetail()
        toast.add({ severity: 'success', summary: '成功', detail: '车队信息已更新', life: 1500 })
    } finally {
        fleetEditSubmitting.value = false
    }
}

async function fetchFleetDetail() {
    if (!Number.isFinite(fleetId.value)) return
    fleetDetail.value = await apiJson<FleetDetail>(`/api/fleets/${fleetId.value}`)
}

function goToDriverDetail(item: { person_id: unknown }) {
    router.push({ path: `/personnels/${normalizeDriverPid(item.person_id)}` })
}

// 车牌号校验（与 VehicleInfo 保持一致）
const vehicle_regex = /^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-HJ-NP-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂港澳]$/

// 分配司机（车辆 -> 司机）
const assignDialogVisible = ref(false)
const assigningVehicle = ref<FleetVehicle | null>(null)
const selectedDriver = ref<Driver | null>(null)
const driverSuggestions = ref<Driver[]>([])
const assigning = ref(false)
const dispatching = ref(false)

type PaginatedResponseRaw<T> = { data: T[]; total: number } | T[]

async function completeFleetDrivers(query: string) {
    if (!Number.isFinite(fleetId.value)) return
    const params = new URLSearchParams({ q: query ?? '', limit: '10', offset: '0' })
    const raw = await apiJson<PaginatedResponseRaw<Driver>>(`/api/fleets/${fleetId.value}/drivers?${params}`)
    const rows = Array.isArray(raw) ? raw : raw.data
    driverSuggestions.value = (rows ?? []) as Driver[]
}

function openAssignDriver(item: FleetVehicle) {
    assigningVehicle.value = item
    selectedDriver.value = null
    driverSuggestions.value = []
    assignDialogVisible.value = true
}

function updateLocalVehicle(vehicle_id: Vehicle['vehicle_id'], patch: VehicleLocalPatch) {
    const idx = vehicles.value.findIndex(v => v.vehicle_id === vehicle_id)
    if (idx < 0) return
    const current = vehicles.value[idx]
    if (!current) return
    vehicles.value[idx] = { ...current, ...patch }
}

function updateLocalDriver(driver_id: Driver['person_id'], patch: DriverLocalPatch) {
    const idx = drivers.value.findIndex(d => d.person_id === driver_id)
    if (idx < 0) return
    const current = drivers.value[idx]
    if (!current) return
    drivers.value[idx] = { ...current, ...patch }
}

async function toggleVehicleMaintenance(item: Vehicle) {
    // 仅允许在 空闲/维修中 之间切换
    const current = String(item.vehicle_status ?? '')
    if (current === '运输中' || current === '装货中') {
        toast.add({ severity: 'warn', summary: '提示', detail: '车辆存在进行中的运单，无法切换维修状态', life: 1500 })
        return
    }
    const nextStatus = current === '维修中' ? '空闲' : '维修中'
    try {
        await updateFleetVehicle(item.vehicle_id, { vehicle_status: nextStatus })
        updateLocalVehicle(item.vehicle_id, { vehicle_status: nextStatus })
        toast.add({ severity: 'success', summary: '成功', detail: `车辆已切换为${nextStatus}`, life: 1500 })
    } catch (e) {
        toast.add({ severity: 'error', summary: '错误', detail: (e as Error).message || '切换失败' })
    }
}

async function toggleDriverLeave(item: Driver) {
    const current = String(item.driver_status ?? '')
    const nextStatus = current === '休息中' ? '空闲' : '休息中'
    try {
        await apiOk(`/api/drivers/${encodeURIComponent(normalizeDriverPid(item.person_id))}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ driver_status: nextStatus }),
        })
        updateLocalDriver(item.person_id, { driver_status: nextStatus })
        toast.add({ severity: 'success', summary: '成功', detail: `司机已切换为${nextStatus}`, life: 1500 })
    } catch (e) {
        toast.add({ severity: 'error', summary: '错误', detail: (e as Error).message || '操作失败' })
    }
}

async function departVehicle(item: FleetVehicle) {
    if (item.driver_id == null) {
        toast.add({ severity: 'warn', summary: '提示', detail: '请先为车辆分配司机', life: 1500 })
        return
    }
    dispatching.value = true
    try {
        await apiOk(`/api/vehicles/${encodeURIComponent(String(item.vehicle_id))}/depart`, { method: 'POST' })
        updateLocalVehicle(item.vehicle_id, { vehicle_status: '运输中' })
        toast.add({ severity: 'success', summary: '成功', detail: '已开始发车', life: 1500 })
    } catch (e) {
        toast.add({ severity: 'error', summary: '错误', detail: (e as Error).message || '操作失败' })
    } finally {
        dispatching.value = false
    }
}

async function deliverVehicle(item: FleetVehicle) {
    dispatching.value = true
    try {
        await apiOk(`/api/vehicles/${encodeURIComponent(String(item.vehicle_id))}/deliver`, { method: 'POST' })
        updateLocalVehicle(item.vehicle_id, { vehicle_status: '空闲' })
        toast.add({ severity: 'success', summary: '成功', detail: '已确认送达', life: 1500 })
    } catch (e) {
        toast.add({ severity: 'error', summary: '错误', detail: (e as Error).message || '操作失败' })
    } finally {
        dispatching.value = false
    }
}

// 安全与效率报表（月度）
type MonthlyReport = { orders: number; incidents: number; fines: number }
const reportMonth = ref<Date | null>(null)
const monthlyOrders = ref(0)
const monthlyIncidents = ref(0)
const monthlyFines = ref(0)
const reportRefreshing = ref(false)

function toMonthString(d: Date | null): string {
    const base = d ?? new Date()
    const y = base.getFullYear()
    const m = `${base.getMonth() + 1}`.padStart(2, '0')
    return `${y}-${m}`
}

async function fetchFleetMonthlyReport() {
    if (!Number.isFinite(fleetId.value)) throw new Error('无效的车队ID')
    reportRefreshing.value = true
    await nextTick()
    const started = performance.now()
    try {
        const params = new URLSearchParams({ month: toMonthString(reportMonth.value) })
        // 拟定后端接口：GET /api/fleets/{fleetId}/reports/monthly?month=YYYY-MM
        const data = await apiJson<MonthlyReport>(`/api/fleets/${fleetId.value}/reports/monthly?${params}`)
        monthlyOrders.value = Number.isFinite(data.orders) ? data.orders : 0
        monthlyIncidents.value = Number.isFinite(data.incidents) ? data.incidents : 0
        monthlyFines.value = Number.isFinite(data.fines) ? data.fines : 0
    } finally {
        const minMs = 300
        const elapsed = performance.now() - started
        if (elapsed < minMs) {
            await new Promise(r => setTimeout(r, minMs - elapsed))
        }
        reportRefreshing.value = false
    }
}

async function searchFleetVehicles(query: string, limit: number, offset: number) {
    if (!Number.isFinite(fleetId.value)) throw new Error('无效的车队ID')
    const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) })
    const data = await apiJson<PaginatedResponse<FleetVehicle>>(`/api/fleets/${fleetId.value}/vehicles?${params}`)
    vehicles.value = data.data
    vehicle_total.value = data.total
}

async function searchFleetDrivers(query: string, limit: number, offset: number) {
    if (!Number.isFinite(fleetId.value)) throw new Error('无效的车队ID')
    const params = new URLSearchParams({ q: query, limit: String(limit), offset: String(offset) })
    const data = await apiJson<PaginatedResponse<Driver>>(`/api/fleets/${fleetId.value}/drivers?${params}`)
    drivers.value = data.data
    driver_total.value = data.total
}

async function createFleetDriver(item: Partial<Driver>) {
    if (!Number.isFinite(fleetId.value)) throw new Error('无效的车队ID')
    const contact = item.person_contact?.trim() ?? ''
    const payload = {
        person_name: String(item.person_name ?? '').trim(),
        person_contact: contact ? contact : null,
        driver_license: String(item.driver_license ?? '').trim(),
    }
    if (!payload.person_name) throw new Error('请填写姓名')
    if (!payload.driver_license) throw new Error('请填写驾照等级')

    await apiOk(`/api/fleets/${fleetId.value}/drivers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
}

async function deleteFleetDriver(driver_id: Driver['person_id']) {
    if (!Number.isFinite(fleetId.value)) throw new Error('无效的车队ID')
    await apiOk(`/api/drivers/${encodeURIComponent(normalizeDriverPid(driver_id))}`, { method: 'DELETE' })
}

async function updateFleetDriver(driver_id: Driver['person_id'], updates: Partial<Driver>) {
    const contact = updates.person_contact?.trim() ?? ''
    const payload = {
        person_name: String(updates.person_name ?? '').trim(),
        person_contact: contact ? contact : null,
        driver_license: String(updates.driver_license ?? '').trim(),
    }
    if (!payload.person_name) throw new Error('请填写姓名')
    if (!payload.driver_license) throw new Error('请填写驾照等级')

    await apiOk(`/api/drivers/${encodeURIComponent(normalizeDriverPid(driver_id))}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
}

async function createFleetVehicle(item: Partial<Vehicle>) {
    if (!Number.isFinite(fleetId.value)) throw new Error('无效的车队ID')
    if (!item.vehicle_id) throw new Error('请填写车牌号')
    if (!vehicle_regex.test(String(item.vehicle_id))) {
        throw new Error(`无效的车牌号格式: ${item.vehicle_id}。示例: 京A12345、沪B6789挂`)
    }
    await apiOk(`/api/fleets/${fleetId.value}/vehicles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...item, fleet_id: fleetId.value }),
    })
}

async function updateFleetVehicle(vehicle_id: Vehicle['vehicle_id'], updates: Partial<Vehicle>) {
    // 直接调用车辆通用更新接口
    await apiOk(`/api/vehicles/${encodeURIComponent(String(vehicle_id))}`,
        {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        }
    )
}

async function assignVehicleDriver(vehicle_id: Vehicle['vehicle_id'], driver_id: string | null) {
    const base = `/api/vehicles/${encodeURIComponent(String(vehicle_id))}/driver`
    const url = driver_id ? `${base}?driver_id=${encodeURIComponent(driver_id)}` : base
    // 后端接口：PATCH /api/vehicles/{vehicle_id}/driver?driver_id=D1 （不传 driver_id 表示解绑）
    await apiOk(url, { method: 'PATCH' })
}

async function assignDriverToVehicle() {
    const v = assigningVehicle.value
    const d = selectedDriver.value
    if (!v) return
    if (!d) {
        toast.add({ severity: 'warn', summary: '提示', detail: '请选择司机', life: 1500 })
        return
    }

    assigning.value = true
    try {
        const driverId = normalizeDriverPid(d.person_id)
        await assignVehicleDriver(v.vehicle_id, driverId)
        const driverNumeric = Number.parseInt(driverId.replace(/^D/i, ''), 10)
        updateLocalVehicle(v.vehicle_id, {
            driver_id: Number.isFinite(driverNumeric) ? driverNumeric : (v.driver_id ?? 0),
            driver_name: d.person_name ?? '',
        })
        assignDialogVisible.value = false
        toast.add({ severity: 'success', summary: '成功', detail: '已分配司机', life: 1500 })
    } catch (e) {
        toast.add({ severity: 'error', summary: '错误', detail: (e as Error).message || '分配失败' })
    } finally {
        assigning.value = false
    }
}

async function unassignDriverFromVehicle(item: FleetVehicle) {
    assigning.value = true
    try {
        await assignVehicleDriver(item.vehicle_id, null)
        updateLocalVehicle(item.vehicle_id, { driver_id: null, driver_name: '' })
        toast.add({ severity: 'success', summary: '成功', detail: '已取消分配', life: 1500 })
    } catch (e) {
        toast.add({ severity: 'error', summary: '错误', detail: (e as Error).message || '取消失败' })
    } finally {
        assigning.value = false
    }
}

async function detachFleetVehicle(vehicle_id: Vehicle['vehicle_id']) {
    // 车队内“删除车辆”：删除车辆记录
    await apiOk(`/api/vehicles/${encodeURIComponent(String(vehicle_id))}`, { method: 'DELETE' })
}

const createFleetDriverColumns: readonly Columns[] = [
    { key: 'person_name', label: '姓名', type: 'text', editable: true, isId: false, required: true },
    { key: 'person_contact', label: '联系方式', type: 'text', editable: true, isId: false, required: false },
    {
        key: 'driver_license',
        label: '驾照等级',
        type: 'select',
        editable: true,
        isId: false,
        required: true,
        options: ['A2', 'B2', 'C1', 'C2', 'C3', 'C4', 'C6'] as const,
    },
] as const

const editFleetDriverColumns: readonly Columns[] = [
    { key: 'person_name', label: '姓名', type: 'text', editable: true, isId: false, required: true },
    { key: 'person_contact', label: '联系方式', type: 'text', editable: true, isId: false, required: false },
    {
        key: 'driver_license',
        label: '驾照等级',
        type: 'select',
        editable: true,
        isId: false,
        required: true,
        options: ['A2', 'B2', 'C1', 'C2', 'C3', 'C4', 'C6'] as const,
    },
] as const

// 在车队中新增车辆：不需要手动录入车队信息（fleet_id 由当前车队自动填充）
const createFleetVehicleColumns: readonly Columns[] = VehicleEditColumns.filter(
    c => c.key !== 'fleet_id' && c.key !== 'fleet_name' && c.key !== 'driver_id' && c.key !== 'driver_name'
)

const driverOps = {
    get data() { return drivers.value },
    get total() { return driver_total.value },
    search: searchFleetDrivers,
    create: async (item: Partial<Driver>) => {
        return createFleetDriver(item)
    },
    delete: async (id: Driver['person_id']) => {
        return deleteFleetDriver(id)
    },
    update: async (id: Driver['person_id'], updates: Partial<Driver>) => {
        return updateFleetDriver(id, updates)
    },
} as const

const vehicleOps = {
    get data() { return vehicles.value },
    get total() { return vehicle_total.value },
    search: searchFleetVehicles,
    // 车队添加车辆：直接创建并绑定到当前车队
    create: async (item: Partial<Vehicle>) => {
        return createFleetVehicle(item)
    },
    update: async (id: Vehicle['vehicle_id'], updates: Partial<Vehicle>) => {
        return updateFleetVehicle(id, updates)
    },
    delete: detachFleetVehicle,
}

const fleetVehicleColumns: readonly Columns[] = VehicleColumns.filter(
    c => c.key !== 'fleet_name' && c.key !== 'fleet_id'
)

const fleetDriverColumns: readonly Columns[] = DriverColumns.filter(
    c => c.key !== 'fleet_name' && c.key !== 'vehicle_id'
)

watch(
    () => fleetId.value,
    () => {
        fleetDetail.value = null
        fetchFleetDetail().catch(() => {
            fleetDetail.value = null
        })
        vehicles.value = []
        vehicle_total.value = 0
        drivers.value = []
        driver_total.value = 0
        // 切换车队时也刷新报表
        fetchFleetMonthlyReport().catch(() => {
            monthlyOrders.value = 0
            monthlyIncidents.value = 0
            monthlyFines.value = 0
        })
    },
    { immediate: true }
)

// 初始化月份为当前月份
if (reportMonth.value == null) {
    reportMonth.value = new Date()
}
</script>

<template>
    <div class="p-6">
        <div class="flex items-center justify-between">
            <h2 class="text-xl font-bold">车队详情</h2>
            <PrimeButton v-if="isAdmin" size="small" label="编辑" @click="openFleetEdit" />
        </div>

        <div class="mt-4 grid grid-cols-2 gap-4">
            <div class="flex flex-col">
                <span class="text-sm text-gray-500">车队ID</span>
                <span class="text-base">{{ Number.isFinite(fleetId) ? fleetId : '-' }}</span>
            </div>
            <div class="flex flex-col">
                <span class="text-sm text-gray-500">车队名</span>
                <span class="text-base">{{ fleetDetail?.fleet_name ?? '-' }}</span>
            </div>
            <div class="flex flex-col">
                <span class="text-sm text-gray-500">调度主管名</span>
                <span class="text-base">{{ fleetDetail?.manager_name ?? '-' }}</span>
            </div>
            <div class="flex flex-col">
                <span class="text-sm text-gray-500">调度主管联系方式</span>
                <span class="text-base">{{ fleetDetail?.manager_contact ?? '-' }}</span>
            </div>
        </div>

        <h3 class="text-xl font-bold mb-4">车辆信息</h3>
        <EntityCardBoard :key="`v-${fleetId}`" :operations="vehicleOps" :columns="fleetVehicleColumns"
            :createColumns="createFleetVehicleColumns" titleKey="vehicle_id" :gridColumns="4"
            :allowCreate="!isManagerReadonly" :allowEdit="!isManagerReadonly" :allowDelete="!isManagerReadonly">
            <template #cardActions="{ item }">
                <PrimeButton v-if="isOperator" size="small" severity="secondary"
                    :label="(item as Vehicle).vehicle_status === '维修中' ? '结束维护' : '维护模式'"
                    @click.stop="toggleVehicleMaintenance(item as Vehicle)" />
                <PrimeButton v-if="(item as Vehicle).vehicle_status === '装货中'" size="small" severity="success"
                    label="开始发车" :loading="dispatching" :disabled="(item as FleetVehicle).driver_id == null"
                    @click.stop="departVehicle(item as FleetVehicle)" />
                <PrimeButton v-else-if="(item as Vehicle).vehicle_status === '运输中'" size="small"
                    severity="success" label="确认送达" :loading="dispatching" @click.stop="deliverVehicle(item as FleetVehicle)" />
                <PrimeButton v-if="(item as FleetVehicle).driver_id == null" size="small" label="分配司机"
                    @click.stop="openAssignDriver(item as FleetVehicle)" />
                <PrimeButton v-else size="small" severity="secondary" label="取消分配司机" :loading="assigning"
                    @click.stop="unassignDriverFromVehicle(item as FleetVehicle)" />
            </template>
        </EntityCardBoard>
        <h3 class="text-xl font-bold mb-4">司机信息</h3>
        <EntityCardBoard :key="`d-${fleetId}`" :operations="driverOps" :columns="fleetDriverColumns"
            :createColumns="createFleetDriverColumns" titleKey="person_name" :gridColumns="4" :allowCreate="isAdmin"
            :editColumns="editFleetDriverColumns" :allowEdit="isAdmin" :allowDelete="isAdmin" :click="goToDriverDetail">
            <template #cardActions="{ item }">
                <PrimeButton v-if="isOperator" size="small" severity="secondary"
                    :label="(item as Driver).driver_status === '休息中' ? '结束休息' : '标记休息中'"
                    @click.stop="toggleDriverLeave(item as Driver)" />
            </template>
        </EntityCardBoard>

        <!-- 安全与效率报表（按月份） -->
        <div class="mt-8 space-y-4">
            <h3 class="text-xl font-bold">安全与效率报表</h3>
            <div class="flex items-center gap-4">
                <div class="flex flex-col">
                    <span class="text-sm text-gray-500">月份</span>
                    <DatePicker v-model="reportMonth" dateFormat="yy-mm" showIcon />
                </div>
                <PrimeButton label="刷新报表" icon="pi pi-refresh" :loading="reportRefreshing" :disabled="reportRefreshing"
                    @click="fetchFleetMonthlyReport" />
            </div>
            <div class="grid grid-cols-3 gap-4">
                <div class="p-4 rounded bg-gray-50 dark:bg-gray-800">
                    <div class="text-sm text-gray-500">已完成运单数</div>
                    <div class="text-2xl font-semibold">{{ monthlyOrders }}</div>
                </div>
                <div class="p-4 rounded bg-gray-50 dark:bg-gray-800">
                    <div class="text-sm text-gray-500">异常事件总数</div>
                    <div class="text-2xl font-semibold">{{ monthlyIncidents }}</div>
                </div>
                <div class="p-4 rounded bg-gray-50 dark:bg-gray-800">
                    <div class="text-sm text-gray-500">累计罚款金额</div>
                    <div class="text-2xl font-semibold">{{ monthlyFines }}</div>
                </div>
            </div>
        </div>
    </div>

    <PrimeDialog v-model:visible="assignDialogVisible" modal header="分配司机" :style="{ width: '32rem' }">
        <div class="flex flex-col gap-2">
            <div class="text-sm text-gray-500">
                车辆：{{ assigningVehicle?.vehicle_id ?? '-' }}
            </div>
            <AutoComplete v-model="selectedDriver" class="w-full" inputClass="w-full" :delay="300"
                :forceSelection="true" :suggestions="driverSuggestions" optionLabel="person_name" :min-length="0"
                :complete-on-focus="true" @complete="completeFleetDrivers($event.query)">
                <template #option="{ option }">
                    <div class="flex flex-col">
                        <span>{{ option?.person_name ?? '' }}</span>
                        <span class="text-xs text-gray-500">工号：{{ option?.person_id ?? '' }}</span>
                    </div>
                </template>
            </AutoComplete>
        </div>
        <template #footer>
            <PrimeButton label="取消" severity="secondary" @click="assignDialogVisible = false" />
            <PrimeButton label="确认" :loading="assigning" @click="assignDriverToVehicle" />
        </template>
    </PrimeDialog>

    <PrimeDialog v-model:visible="fleetEditVisible" modal header="编辑车队信息" :style="{ width: '40rem' }">
        <div class="grid grid-cols-2 gap-4">
            <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">车队名*</label>
                <InputText v-model="editFleetName" />
            </div>
            <div class="flex flex-col gap-2">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">调度主管姓名*</label>
                <InputText v-model="editManagerName" />
            </div>
            <div class="flex flex-col gap-2 col-span-2">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">调度主管联系方式</label>
                <InputText v-model="editManagerContact" />
            </div>
        </div>

        <template #footer>
            <PrimeButton label="取消" severity="secondary" @click="fleetEditVisible = false" />
            <PrimeButton label="确认" :loading="fleetEditSubmitting" @click="confirmFleetEdit" />
        </template>
    </PrimeDialog>
</template>