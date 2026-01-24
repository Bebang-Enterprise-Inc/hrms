<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/store/receiving" />
				</ion-buttons>
				<ion-title>Receive Delivery</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div v-if="loading" class="flex justify-center p-8">
				<ion-spinner />
			</div>

			<template v-else>
				<!-- Trip Info Header -->
				<div class="p-4 bg-blue-50 border-b">
					<h2 class="font-bold">Trip: {{ trip }}</h2>
					<p class="text-gray-600">Receiving delivery items</p>
				</div>

				<!-- Items Checklist -->
				<ion-list>
					<ion-list-header>
						<ion-label>Items Checklist</ion-label>
					</ion-list-header>

					<ion-item v-for="(item, index) in receivingItems" :key="index">
						<div class="py-3 w-full">
							<div class="flex justify-between items-center mb-2">
								<span class="font-medium">{{ item.item_code }}</span>
								<span class="text-gray-500">Expected: {{ item.expected_qty }}</span>
							</div>

							<!-- Quantity Input -->
							<div class="flex items-center gap-2 mb-2">
								<span class="text-sm">Received:</span>
								<ion-input
									type="number"
									v-model.number="item.received_qty"
									class="w-20 border rounded px-2"
								/>
							</div>

							<!-- Quality Checks -->
							<div class="grid grid-cols-2 gap-2 text-sm">
								<ion-checkbox v-model="item.check_condition" label-placement="end">
									Condition OK
								</ion-checkbox>
								<ion-checkbox v-model="item.check_packaging" label-placement="end">
									Packaging OK
								</ion-checkbox>
								<ion-checkbox v-model="item.check_expiry" label-placement="end">
									Expiry OK
								</ion-checkbox>
								<ion-checkbox v-model="item.check_temperature" label-placement="end">
									Temperature OK
								</ion-checkbox>
							</div>

							<!-- Report Issue Button -->
							<ion-button
								v-if="hasIssue(item)"
								size="small"
								fill="outline"
								color="danger"
								@click="reportFQI(item)"
								class="mt-2"
							>
								Report Issue (FQI)
							</ion-button>
						</div>
					</ion-item>
				</ion-list>

				<!-- Signatures Section -->
				<div class="p-4 border-t">
					<h3 class="font-medium mb-3">Signatures Required</h3>
					<div class="space-y-3">
						<ion-item>
							<ion-label position="stacked">Receiver 1 (Supervisor)</ion-label>
							<ion-input placeholder="Tap to sign" readonly />
						</ion-item>
						<ion-item>
							<ion-label position="stacked">Receiver 2 (Staff)</ion-label>
							<ion-input placeholder="Tap to sign" readonly />
						</ion-item>
						<ion-item>
							<ion-label position="stacked">Driver</ion-label>
							<ion-input placeholder="Tap to sign" readonly />
						</ion-item>
					</div>
				</div>

				<!-- Submit Button -->
				<div class="p-4">
					<ion-button expand="block" @click="submitReceiving" :disabled="submitting">
						<ion-spinner v-if="submitting" slot="start" />
						Complete Receiving
					</ion-button>
				</div>
			</template>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonList, IonListHeader, IonLabel, IonItem,
	IonSpinner, IonButton, IonInput, IonCheckbox
} from "@ionic/vue"
import { ref, computed, inject, onMounted } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"

const router = useRouter()
const employee = inject("$employee")

const props = defineProps({
	trip: { type: String, required: true }
})

const loading = ref(true)
const submitting = ref(false)
const receivingItems = ref([])

// Get store from employee's branch
const store = computed(() => employee.data?.branch || "")

function hasIssue(item) {
	return item.received_qty !== item.expected_qty ||
		!item.check_condition ||
		!item.check_packaging ||
		!item.check_expiry ||
		!item.check_temperature
}

function reportFQI(item) {
	router.push({
		path: "/store/fqi/new",
		query: {
			trip: props.trip,
			item_code: item.item_code,
			expected_qty: item.expected_qty,
			actual_qty: item.received_qty
		}
	})
}

async function loadTripItems() {
	loading.value = true
	try {
		// For now, create mock items - in production this would come from the trip
		receivingItems.value = [
			{ item_code: "SKU-001", expected_qty: 10, received_qty: 10, check_condition: true, check_packaging: true, check_expiry: true, check_temperature: true },
			{ item_code: "SKU-002", expected_qty: 5, received_qty: 5, check_condition: true, check_packaging: true, check_expiry: true, check_temperature: true },
		]
	} catch (error) {
		console.error("Failed to load trip items:", error)
	} finally {
		loading.value = false
	}
}

async function submitReceiving() {
	submitting.value = true
	try {
		const items = receivingItems.value.map(item => ({
			item_code: item.item_code,
			expected_qty: item.expected_qty,
			received_qty: item.received_qty,
			check_condition: item.check_condition ? 1 : 0,
			check_packaging: item.check_packaging ? 1 : 0,
			check_expiry: item.check_expiry ? 1 : 0,
			check_temperature: item.check_temperature ? 1 : 0,
			has_issue: hasIssue(item) ? 1 : 0
		}))

		const result = await call("hrms.api.store.complete_receiving", {
			store: store.value,
			trip: props.trip,
			items: JSON.stringify(items)
		})

		if (result?.success) {
			router.push("/store/receiving")
		}
	} catch (error) {
		console.error("Failed to submit receiving:", error)
	} finally {
		submitting.value = false
	}
}

onMounted(() => {
	loadTripItems()
})
</script>
