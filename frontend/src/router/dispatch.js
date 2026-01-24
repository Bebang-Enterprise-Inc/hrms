// Dispatch Tracker Routes
// Handles warehouse dispatch and driver operations

export default [
	{
		path: "/dispatch",
		name: "DispatchDashboard",
		component: () => import("@/views/dispatch/Dashboard.vue"),
		meta: { requiresAuth: true, title: "Dispatch Tracker" },
	},
	{
		path: "/dispatch/trip/:id",
		name: "TripDetail",
		component: () => import("@/views/dispatch/TripDetail.vue"),
		meta: { requiresAuth: true, title: "Trip Details" },
	},
	{
		path: "/dispatch/trip/:id/departure",
		name: "DepartureChecklist",
		component: () => import("@/views/dispatch/DepartureForm.vue"),
		meta: { requiresAuth: true, title: "Departure Checklist" },
	},
	{
		path: "/dispatch/trip/:id/stop/:stopIdx",
		name: "DeliveryStop",
		component: () => import("@/views/dispatch/DeliveryStop.vue"),
		meta: { requiresAuth: true, title: "Delivery Stop" },
	},
]
