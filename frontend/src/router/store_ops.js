// Store Operations Routes
// Handles store ordering, receiving, and FQI reports

export default [
	{
		path: "/store/ordering",
		name: "StoreOrdering",
		component: () => import("@/views/store_ops/Ordering.vue"),
		meta: { requiresAuth: true, title: "Store Ordering" },
	},
	{
		path: "/store/ordering/new",
		name: "NewOrder",
		component: () => import("@/views/store_ops/OrderForm.vue"),
		meta: { requiresAuth: true, title: "New Order" },
	},
	{
		path: "/store/ordering/:id",
		name: "OrderDetail",
		component: () => import("@/views/store_ops/OrderDetail.vue"),
		meta: { requiresAuth: true, title: "Order Details" },
	},
	{
		path: "/store/receiving",
		name: "StoreReceiving",
		component: () => import("@/views/store_ops/Receiving.vue"),
		meta: { requiresAuth: true, title: "Store Receiving" },
	},
	{
		path: "/store/receiving/:trip",
		name: "ReceivingDetail",
		component: () => import("@/views/store_ops/ReceivingForm.vue"),
		meta: { requiresAuth: true, title: "Receive Delivery" },
	},
	{
		path: "/store/fqi",
		name: "FQIReports",
		component: () => import("@/views/store_ops/FQIList.vue"),
		meta: { requiresAuth: true, title: "FQI Reports" },
	},
	{
		path: "/store/fqi/new",
		name: "NewFQI",
		component: () => import("@/views/store_ops/FQIForm.vue"),
		meta: { requiresAuth: true, title: "Report FQI" },
	},
]
