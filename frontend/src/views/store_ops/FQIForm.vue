<template>
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/store/fqi" />
				</ion-buttons>
				<ion-title>Report FQI</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content :fullscreen="true">
			<div class="p-4">
				<!-- Issue Type -->
				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Issue Type *</ion-label>
					<ion-select v-model="fqi.issue_type" interface="action-sheet" placeholder="Select issue type">
						<ion-select-option value="Shortage">Shortage</ion-select-option>
						<ion-select-option value="Damage">Damage</ion-select-option>
						<ion-select-option value="Wrong Item">Wrong Item</ion-select-option>
						<ion-select-option value="Quality">Quality Issue</ion-select-option>
						<ion-select-option value="Temperature">Temperature Issue</ion-select-option>
						<ion-select-option value="Expiry">Expiry Issue</ion-select-option>
					</ion-select>
				</div>

				<!-- Item Code -->
				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Item Code</ion-label>
					<ion-input v-model="fqi.item_code" placeholder="Enter item code" />
				</div>

				<!-- Expected vs Actual Qty -->
				<div class="grid grid-cols-2 gap-4 mb-4">
					<div>
						<ion-label class="text-sm text-gray-600 mb-1 block">Expected Qty</ion-label>
						<ion-input type="number" v-model.number="fqi.expected_qty" />
					</div>
					<div>
						<ion-label class="text-sm text-gray-600 mb-1 block">Actual Qty</ion-label>
						<ion-input type="number" v-model.number="fqi.actual_qty" />
					</div>
				</div>

				<!-- Description -->
				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Description *</ion-label>
					<ion-textarea
						v-model="fqi.description"
						placeholder="Describe the issue in detail..."
						:rows="4"
					/>
				</div>

				<!-- Photo Upload -->
				<div class="mb-4">
					<ion-label class="text-sm text-gray-600 mb-1 block">Photo Evidence</ion-label>
					<div class="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
						<ion-icon :icon="cameraOutline" class="text-4xl text-gray-400 mb-2" />
						<p class="text-gray-500">Tap to take photo</p>
						<input type="file" accept="image/*" capture="environment" class="hidden" ref="photoInput" />
					</div>
				</div>

				<!-- Submit Button -->
				<ion-button expand="block" @click="submitFQI" :disabled="!canSubmit || submitting">
					<ion-spinner v-if="submitting" slot="start" />
					Submit FQI Report
				</ion-button>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import {
	IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
	IonBackButton, IonButton, IonInput, IonLabel, IonSelect,
	IonSelectOption, IonTextarea, IonSpinner, IonIcon
} from "@ionic/vue"
import { cameraOutline } from "ionicons/icons"
import { ref, computed, inject, onMounted } from "vue"
import { useRouter, useRoute } from "vue-router"
import { call } from "frappe-ui"

const router = useRouter()
const route = useRoute()
const employee = inject("$employee")

const submitting = ref(false)
const photoInput = ref(null)

// Get store from employee's branch
const store = computed(() => employee.data?.branch || "")

const fqi = ref({
	issue_type: "",
	item_code: "",
	expected_qty: null,
	actual_qty: null,
	description: "",
	receiving: null
})

const canSubmit = computed(() => {
	return fqi.value.issue_type && fqi.value.description
})

async function submitFQI() {
	if (!canSubmit.value) return

	submitting.value = true
	try {
		const result = await call("hrms.api.store.create_fqi_report", {
			store: store.value,
			receiving: fqi.value.receiving,
			item_code: fqi.value.item_code,
			issue_type: fqi.value.issue_type,
			description: fqi.value.description,
			expected_qty: fqi.value.expected_qty,
			actual_qty: fqi.value.actual_qty
		})

		if (result?.success) {
			router.push("/store/fqi")
		}
	} catch (error) {
		console.error("Failed to submit FQI:", error)
	} finally {
		submitting.value = false
	}
}

onMounted(() => {
	// Pre-fill from query params if coming from receiving
	if (route.query.trip) {
		fqi.value.receiving = route.query.trip
	}
	if (route.query.item_code) {
		fqi.value.item_code = route.query.item_code
	}
	if (route.query.expected_qty) {
		fqi.value.expected_qty = parseFloat(route.query.expected_qty)
	}
	if (route.query.actual_qty) {
		fqi.value.actual_qty = parseFloat(route.query.actual_qty)
	}
})
</script>
