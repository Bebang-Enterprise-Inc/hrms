<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/store/ordering" />
				</ion-buttons>
				<ion-title>Order {{ id }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div v-if="loading" class="flex justify-center p-8">
				<ion-spinner />
			</div>

			<template v-else-if="order">
				<!-- Order Header -->
				<div class="p-4 bg-gray-50 border-b">
					<div class="flex justify-between items-center">
						<div>
							<h2 class="text-lg font-bold">{{ order.name }}</h2>
							<p class="text-gray-500">{{ order.order_date }}</p>
						</div>
						<ion-badge :color="getStatusColor(order.status)">
							{{ order.status }}
						</ion-badge>
					</div>
					<div class="mt-2 text-sm text-gray-600">
						<p>Store: {{ order.store }}</p>
						<p>Delivery Date: {{ order.delivery_date }}</p>
					</div>
				</div>

				<!-- Order Items -->
				<ion-list>
					<ion-list-header>
						<ion-label>Order Items</ion-label>
					</ion-list-header>
					<ion-item v-for="item in order.items" :key="item.item_code">
						<ion-label>
							<h2>{{ item.item_name || item.item_code }}</h2>
							<p>{{ item.uom }}</p>
						</ion-label>
						<div slot="end" class="text-right">
							<div class="font-bold">{{ item.qty_requested }}</div>
							<div v-if="item.qty_approved" class="text-sm text-green-600">
								Approved: {{ item.qty_approved }}
							</div>
						</div>
					</ion-item>
				</ion-list>

				<!-- Actions -->
				<div v-if="order.status === 'Draft'" class="p-4">
					<ion-button expand="block" @click="submitForApproval">
						Submit for Approval
					</ion-button>
				</div>
			</template>

			<EmptyState v-else message="Order not found" />
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonList, IonListHeader, IonLabel, IonItem,
	IonSpinner, IonBadge, IonButton
} from "@ionic/vue"
import { ref, onMounted } from "vue"
import { call } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"

const props = defineProps({
	id: { type: String, required: true }
})

const loading = ref(true)
const order = ref(null)

async function fetchOrder() {
	loading.value = true
	try {
		const result = await call("frappe.client.get", {
			doctype: "BEI Store Order",
			name: props.id
		})
		order.value = result
	} catch (error) {
		console.error("Failed to fetch order:", error)
	} finally {
		loading.value = false
	}
}

function getStatusColor(status) {
	const colors = {
		"Draft": "medium",
		"Pending Approval": "warning",
		"Approved": "success",
		"Partial": "tertiary",
		"Delivered": "primary"
	}
	return colors[status] || "medium"
}

async function submitForApproval() {
	try {
		await call("frappe.client.set_value", {
			doctype: "BEI Store Order",
			name: props.id,
			fieldname: "status",
			value: "Pending Approval"
		})
		await fetchOrder()
	} catch (error) {
		console.error("Failed to submit order:", error)
	}
}

onMounted(() => {
	fetchOrder()
})
</script>
