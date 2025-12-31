interface FieldDef {
    key: string
    label: string
    type: 'text' | 'number' | 'select' | 'foreign' | 'date'
    editable?: boolean // 可缺省，默认true
    isId?: boolean // 可缺省，默认false
    required?: boolean // 是否必填，默认为 true
    options?: readonly string[]
    // suggestions：用于“可自定义的下拉建议”，UI 可用 AutoComplete（forceSelection=false）
    suggestions?: readonly string[]
    // foreign：用于“外键选择”，UI 可用 AutoComplete 进行远程搜索
    foreign?: {
        endpoint: string
        valueKey: string
        labelKey: string
        queryParam?: string // 默认 q
        limitParam?: string // 默认 limit
        offsetParam?: string // 默认 offset
    }
}

export interface Columns extends Omit<FieldDef, 'editable' | 'isId'> {
    editable: boolean
    isId: boolean
}

export interface TableOperations<T, IdKey extends keyof T> {
    readonly data: T[]
    readonly total: number
    search: (query: string, limit: number, offset: number) => Promise<void>
    // 允许“用户输入主键”的创建场景：当主键列 editable=true 时，DBtable 会把主键也一并提交
    create?: (item: Partial<T>) => Promise<void>
    update?: (id: T[IdKey], updates: Partial<T>) => Promise<void>
    delete?: (id: T[IdKey]) => Promise<void>
}

interface FieldTypeMap {
    text: string
    number: number
    select: string
    // 外键字段最终提交的是 id（可能是 number 或 string）
    foreign: string | number | null
    date: string
}

type InferModelType<T extends readonly FieldDef[]> = {
    [K in T[number] as K['key']]: FieldTypeMap[K['type']]
}

const normalizeField = (field: FieldDef) => ({
    ...field,
    editable: field.editable ?? true,
    isId: field.isId ?? false,
    required: field.required ?? true,
})

const PersonnelSchema = [
    { key: 'person_id', label: '工号', type: 'text', isId: true, editable: false },
    { key: 'person_name', label: '姓名', type: 'text' },
    { key: 'person_contact', label: '联系方式', type: 'text', required: false },
] as const satisfies readonly FieldDef[]

const DriverSchema = [
    ...PersonnelSchema,
    {
        key: 'driver_license',
        label: '驾照等级',
        type: 'select',
        options: ['A2', 'B2', 'C1', 'C2', 'C3', 'C4', 'C6'],
    },
    { key: 'driver_status', label: '状态', type: 'text', editable: false }, // '空闲' | '运输中' | '休息中'
    { key: 'fleet_name', label: '所属车队', type: 'text', editable: false },
    { key: 'vehicle_id', label: '驾驶车辆', type: 'text', editable: false, required: false },
] as const satisfies readonly FieldDef[]

const FleetManagerSchema = [
    ...PersonnelSchema,
    { key: 'fleet_name', label: '所属车队', type: 'text', editable: false },
] as const satisfies readonly FieldDef[]

const VehicleSchema = [
    { key: 'vehicle_id', label: '车牌号', type: 'text', isId: true },
    { key: 'driver_name', label: '司机', type: 'text', editable: false, required: false },
    { key: 'fleet_name', label: '所属车队', type: 'text', editable: false, required: false },
    {
        key: 'fleet_id',
        label: '所属车队',
        type: 'foreign',
        required: true,
        foreign: {
            endpoint: '/api/fleets',
            valueKey: 'fleet_id',
            labelKey: 'fleet_name',
        },
    },
    { key: 'max_weight', label: '载重上限', type: 'number' },
    { key: 'max_volume', label: '容积上限', type: 'number' },
    {
        key: 'remaining_weight',
        label: '剩余载重',
        type: 'number',
        editable: false,
        required: false,
    },
    {
        key: 'remaining_volume',
        label: '剩余容积',
        type: 'number',
        editable: false,
        required: false,
    },
    {
        key: 'vehicle_status',
        label: '状态',
        type: 'select',
        options: ['空闲', '装货中','运输中', '维修中'],
        editable: false,
        required: false,
    },
] as const satisfies readonly FieldDef[]

const OrderSchema = [
    { key: 'order_id', label: '订单号', type: 'number', isId: true, editable: false },
    { key: 'origin', label: '始发地', type: 'text' },
    { key: 'destination', label: '目的地', type: 'text' },
    { key: 'weight', label: '货物重量', type: 'number' },
    { key: 'volume', label: '货物体积', type: 'number' },
    {
        key: 'vehicle_id',
        label: '车牌号',
        type: 'foreign',
        required: false,
        foreign: {
            endpoint: '/api/vehicles',
            valueKey: 'vehicle_id',
            labelKey: 'vehicle_id',
        },
    },
    {
        key: 'status',
        label: '状态',
        type: 'select',
        options: ['待处理', '装货中', '运输中', '已完成', '已取消'],
    },
] as const satisfies readonly FieldDef[]

const IncidentSchema = [
    { key: 'incident_id', label: '异常事件ID', type: 'number', isId: true, editable: false },
    {
        key: 'driver_id',
        label: '关联司机',
        type: 'foreign',
        foreign: {
            endpoint: '/api/drivers',
            valueKey: 'person_id',
            labelKey: 'person_name',
        },
    },
    {
        key: 'vehicle_id',
        label: '车辆',
        type: 'foreign',
        foreign: {
            endpoint: '/api/vehicles',
            valueKey: 'vehicle_id',
            labelKey: 'vehicle_id',
        },
    },
    { key: 'timestamp', label: '时间', type: 'date' },
    { key: 'type', label: '异常类型', type: 'select', options: ['运输中异常', '空闲时异常'] },
    {
        key: 'description',
        label: '异常描述',
        type: 'text',
        suggestions: ['货物破损', '车辆故障', '严重延误', '超速报警'],
    },
    { key: 'fine_amount', label: '罚款金额', type: 'number' },
    { key: 'status', label: '异常处理状态', type: 'select', options: ['未处理', '已处理'] },
] as const satisfies readonly FieldDef[]

const FleetSchema = [
    { key: 'fleet_id', label: '车队ID', type: 'number', isId: true, editable: false },
    { key: 'fleet_name', label: '车队名称', type: 'text' },
    {
        key: 'manager_id',
        label: '调度主管',
        type: 'foreign',
        foreign: {
            endpoint: '/api/personnels',
            valueKey: 'person_id',
            labelKey: 'person_name',
        },
    },
] as const satisfies readonly FieldDef[]

const DistributionCenterSchema = [
    { key: 'center_id', label: '配送中心ID', type: 'number', isId: true, editable: false },
    { key: 'center_name', label: '配送中心名称', type: 'text' },
] as const satisfies readonly FieldDef[]

export type Driver = InferModelType<typeof DriverSchema>
export const DriverColumns = DriverSchema.map(normalizeField)

export type Vehicle = InferModelType<typeof VehicleSchema>
export const VehicleColumns = VehicleSchema.map(normalizeField)
export const VehicleCardColumns = VehicleColumns.filter((c) => c.key !== 'fleet_id')
export const VehicleEditColumns = VehicleColumns.filter((c) => c.key !== 'fleet_name')

export type Order = InferModelType<typeof OrderSchema>
export const OrderColumns = OrderSchema.map(normalizeField)

export type Incident = InferModelType<typeof IncidentSchema>
export const IncidentColumns = IncidentSchema.map(normalizeField)

export type Fleet = InferModelType<typeof FleetSchema>
export const FleetColumns = FleetSchema.map(normalizeField)

export type DistributionCenter = InferModelType<typeof DistributionCenterSchema>
export const DistributionCenterColumns = DistributionCenterSchema.map(normalizeField)

export type Personnel = InferModelType<typeof PersonnelSchema>
export const PersonnelColumns = PersonnelSchema.map(normalizeField)

export type FleetManager = InferModelType<typeof FleetManagerSchema>
export const FleetManagerColumns = FleetManagerSchema.map(normalizeField)
