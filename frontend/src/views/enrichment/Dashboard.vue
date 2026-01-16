<template>
	<BaseLayout pageTitle="Data Verification">
		<template #body>
			<div class="flex flex-col mt-4 mb-7 p-4 gap-6">
				<!-- Summary Cards -->
				<div class="grid grid-cols-2 gap-3">
					<div class="bg-blue-50 rounded-lg p-4">
						<div class="text-2xl font-bold text-blue-700">{{ stats.total }}</div>
						<div class="text-sm text-blue-600">Total Employees</div>
					</div>
					<div class="bg-green-50 rounded-lg p-4">
						<div class="text-2xl font-bold text-green-700">{{ stats.verified }}</div>
						<div class="text-sm text-green-600">Verified</div>
					</div>
					<div class="bg-yellow-50 rounded-lg p-4">
						<div class="text-2xl font-bold text-yellow-700">{{ stats.pending }}</div>
						<div class="text-sm text-yellow-600">Pending</div>
					</div>
					<div class="bg-red-50 rounded-lg p-4">
						<div class="text-2xl font-bold text-red-700">{{ stats.issues }}</div>
						<div class="text-sm text-red-600">Has Issues</div>
					</div>
				</div>

				<!-- Progress Bar -->
				<div class="bg-white rounded-lg p-4 shadow-sm">
					<div class="flex justify-between items-center mb-2">
						<span class="text-sm font-medium text-gray-700">Overall Progress</span>
						<span class="text-sm font-bold text-gray-900">{{ stats.progress_pct }}%</span>
					</div>
					<div class="w-full bg-gray-200 rounded-full h-3">
						<div
							class="bg-green-500 h-3 rounded-full transition-all duration-500"
							:style="{ width: stats.progress_pct + '%' }"
						></div>
					</div>
				</div>

				<!-- Store Filter -->
				<div v-if="userStores?.data?.length > 1" class="bg-white rounded-lg p-4 shadow-sm">
					<label class="text-sm font-medium text-gray-700 mb-2 block">Filter by Store</label>
					<select
						v-model="selectedStore"
						@change="refreshData"
						class="w-full p-3 border rounded-lg text-gray-700"
					>
						<option value="">All Stores</option>
						<option v-for="store in userStores.data" :key="store" :value="store">
							{{ store }}
						</option>
					</select>
				</div>

				<!-- Employee List -->
				<div>
					<div class="text-lg text-gray-800 font-bold mb-3">Employees to Verify</div>
					<div v-if="enrichmentData?.loading" class="text-center py-8 text-gray-500">
						Loading...
					</div>
					<div v-else-if="employees.length === 0" class="text-center py-8 text-gray-500">
						No employees found
					</div>
					<div v-else class="space-y-3">
						<div
							v-for="emp in employees"
							:key="emp.name"
							class="bg-white rounded-lg p-4 shadow-sm"
							@click="showEmployeeDetails(emp)"
						>
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-3">
									<div
										class="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 font-bold"
									>
										{{ getInitials(emp.employee_name) }}
									</div>
									<div>
										<div class="font-medium text-gray-900">{{ emp.employee_name }}</div>
										<div class="text-sm text-gray-500">{{ emp.branch || 'No Branch' }}</div>
									</div>
								</div>
								<div>
									<span
										:class="getStatusClass(emp.custom_verification_status)"
										class="px-2 py-1 rounded-full text-xs font-medium"
									>
										{{ emp.custom_verification_status || 'Pending' }}
									</span>
								</div>
							</div>
						</div>
					</div>
				</div>

				<!-- Store Progress (for HR) -->
				<div v-if="showStoreProgress">
					<div class="text-lg text-gray-800 font-bold mb-3">Progress by Store</div>
					<div class="space-y-3">
						<div
							v-for="store in storeProgress?.data"
							:key="store.branch"
							class="bg-white rounded-lg p-3 shadow-sm"
						>
							<div class="flex justify-between items-center mb-2">
								<span class="text-sm font-medium text-gray-700">{{ store.branch }}</span>
								<span class="text-sm text-gray-600">
									{{ store.verified }}/{{ store.total }} ({{ store.progress_pct }}%)
								</span>
							</div>
							<div class="w-full bg-gray-200 rounded-full h-2">
								<div
									class="h-2 rounded-full transition-all duration-500"
									:class="getProgressColor(store.progress_pct)"
									:style="{ width: store.progress_pct + '%' }"
								></div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>

	<!-- Employee Details Modal -->
	<ion-modal :is-open="showModal" @did-dismiss="showModal = false">
		<ion-header>
			<ion-toolbar>
				<ion-title>Employee Details</ion-title>
				<ion-buttons slot="end">
					<ion-button @click="showModal = false">Close</ion-button>
				</ion-buttons>
			</ion-toolbar>
		</ion-header>
		<ion-content class="ion-padding">
			<div v-if="selectedEmployee" class="space-y-4">
				<div class="text-center mb-4">
					<div
						class="w-20 h-20 mx-auto rounded-full bg-gray-200 flex items-center justify-center text-gray-600 text-2xl font-bold"
					>
						{{ getInitials(selectedEmployee.employee_name) }}
					</div>
					<div class="text-xl font-bold mt-2">{{ selectedEmployee.employee_name }}</div>
					<div class="text-gray-500">{{ selectedEmployee.designation || 'No Designation' }}</div>
				</div>

				<div class="space-y-3">
					<div class="flex justify-between py-2 border-b">
						<span class="text-gray-500">Branch</span>
						<span class="font-medium">{{ selectedEmployee.branch || 'N/A' }}</span>
					</div>
					<div class="flex justify-between py-2 border-b">
						<span class="text-gray-500">Department</span>
						<span class="font-medium">{{ selectedEmployee.department || 'N/A' }}</span>
					</div>
					<div class="flex justify-between py-2 border-b">
						<span class="text-gray-500">Bio ID</span>
						<span class="font-medium">{{ selectedEmployee.attendance_device_id || 'N/A' }}</span>
					</div>
					<div class="flex justify-between py-2 border-b">
						<span class="text-gray-500">Phone</span>
						<span class="font-medium">{{ selectedEmployee.cell_number || 'N/A' }}</span>
					</div>
					<div class="flex justify-between py-2 border-b">
						<span class="text-gray-500">Email</span>
						<span class="font-medium">{{ selectedEmployee.personal_email || 'N/A' }}</span>
					</div>
					<div class="flex justify-between py-2 border-b">
						<span class="text-gray-500">Status</span>
						<span
							:class="getStatusClass(selectedEmployee.custom_verification_status)"
							class="px-2 py-1 rounded-full text-xs font-medium"
						>
							{{ selectedEmployee.custom_verification_status || 'Pending' }}
						</span>
					</div>
				</div>

				<!-- Action Buttons -->
				<div class="space-y-3 mt-6">
					<Button
						v-if="selectedEmployee.custom_verification_status !== 'Verified'"
						variant="solid"
						class="w-full py-4"
						@click="markAsVerified"
						:loading="verifyingEmployee"
					>
						Mark as Verified
					</Button>
					<Button
						v-if="selectedEmployee.custom_verification_status !== 'Has Issues'"
						variant="outline"
						class="w-full py-4"
						@click="showIssueForm = true"
					>
						Report Issue
					</Button>
				</div>

				<!-- Issue Form -->
				<div v-if="showIssueForm" class="mt-4 p-4 bg-gray-50 rounded-lg">
					<div class="text-sm font-medium text-gray-700 mb-2">Issue Type</div>
					<select v-model="issueType" class="w-full p-3 border rounded-lg mb-3">
						<option value="">Select issue type...</option>
						<option value="Wrong Name">Wrong Name</option>
						<option value="Wrong Store">Wrong Store</option>
						<option value="Missing Info">Missing Info</option>
						<option value="Duplicate">Duplicate</option>
						<option value="Other">Other</option>
					</select>
					<div class="text-sm font-medium text-gray-700 mb-2">Description</div>
					<textarea
						v-model="issueDescription"
						class="w-full p-3 border rounded-lg"
						rows="3"
						placeholder="Describe the issue..."
					></textarea>
					<Button
						variant="solid"
						class="w-full py-4 mt-3 bg-red-500"
						@click="submitIssue"
						:loading="reportingIssue"
					>
						Submit Issue
					</Button>
				</div>
			</div>
		</ion-content>
	</ion-modal>
</template>

<script setup>
import { ref, computed, inject } from "vue"
import { createResource } from "frappe-ui"
import { IonModal, IonHeader, IonToolbar, IonTitle, IonButtons, IonButton, IonContent } from "@ionic/vue"

import BaseLayout from "@/components/BaseLayout.vue"

const employee = inject("$employee")

// State
const selectedStore = ref("")
const showModal = ref(false)
const selectedEmployee = ref(null)
const showIssueForm = ref(false)
const issueType = ref("")
const issueDescription = ref("")
const verifyingEmployee = ref(false)
const reportingIssue = ref(false)

// API Resources
const userStores = createResource({
	url: "hrms.api.enrichment.get_user_stores",
	auto: true,
})

const enrichmentData = createResource({
	url: "hrms.api.enrichment.get_enrichment_dashboard",
	auto: true,
	makeParams() {
		return {
			store: selectedStore.value || null,
		}
	},
})

const storeProgress = createResource({
	url: "hrms.api.enrichment.get_store_progress",
	auto: true,
})

// Computed
const stats = computed(() => enrichmentData.data?.stats || { total: 0, verified: 0, pending: 0, issues: 0, progress_pct: 0 })
const employees = computed(() => enrichmentData.data?.employees || [])
const showStoreProgress = computed(() => userStores.data?.length > 1)

// Methods
function refreshData() {
	enrichmentData.fetch()
}

function getInitials(name) {
	if (!name) return "?"
	return name
		.split(" ")
		.slice(0, 2)
		.map((n) => n[0])
		.join("")
		.toUpperCase()
}

function getStatusClass(status) {
	switch (status) {
		case "Verified":
			return "bg-green-100 text-green-800"
		case "Has Issues":
			return "bg-red-100 text-red-800"
		default:
			return "bg-yellow-100 text-yellow-800"
	}
}

function getProgressColor(pct) {
	if (pct >= 90) return "bg-green-500"
	if (pct >= 50) return "bg-yellow-500"
	return "bg-red-500"
}

function showEmployeeDetails(emp) {
	selectedEmployee.value = emp
	showIssueForm.value = false
	issueType.value = ""
	issueDescription.value = ""
	showModal.value = true
}

async function markAsVerified() {
	verifyingEmployee.value = true
	try {
		await createResource({
			url: "hrms.api.enrichment.mark_employee_verified",
			params: {
				employee: selectedEmployee.value.name,
			},
		}).fetch()
		selectedEmployee.value.custom_verification_status = "Verified"
		enrichmentData.fetch()
	} catch (e) {
		console.error(e)
	} finally {
		verifyingEmployee.value = false
	}
}

async function submitIssue() {
	if (!issueType.value || !issueDescription.value) {
		alert("Please fill in all fields")
		return
	}
	reportingIssue.value = true
	try {
		await createResource({
			url: "hrms.api.enrichment.report_employee_issue",
			params: {
				employee: selectedEmployee.value.name,
				issue_type: issueType.value,
				description: issueDescription.value,
			},
		}).fetch()
		selectedEmployee.value.custom_verification_status = "Has Issues"
		showIssueForm.value = false
		enrichmentData.fetch()
	} catch (e) {
		console.error(e)
	} finally {
		reportingIssue.value = false
	}
}
</script>
