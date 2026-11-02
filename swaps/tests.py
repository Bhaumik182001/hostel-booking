from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import StudentProfile
from rooms.models import HostelBlock, Room
from swaps.models import SwapRequest
from swaps.forms import SwapRequestCreateForm


class SwapRequestFormValidationTests(TestCase):
    def setUp(self):
        # Create blocks
        self.block_male = HostelBlock.objects.create(name='Boys Block A', gender_restriction='M')
        self.block_female = HostelBlock.objects.create(name='Girls Block B', gender_restriction='F')
        self.block_coed = HostelBlock.objects.create(name='Coed Block C', gender_restriction='C')

        # Create rooms
        self.room_m1 = Room.objects.create(block=self.block_male, room_number='101', capacity=2)
        self.room_m2 = Room.objects.create(block=self.block_male, room_number='102', capacity=2)
        self.room_f1 = Room.objects.create(block=self.block_female, room_number='201', capacity=2)
        self.room_c1 = Room.objects.create(block=self.block_coed, room_number='301', capacity=2)

        # Create student 1 in Male Room 101
        self.user1 = User.objects.create_user(username='john', password='Pass1234!')
        self.student1 = StudentProfile.objects.create(user=self.user1, current_room=self.room_m1)

        # Create student without allocation
        self.user_unallocated = User.objects.create_user(username='homeless', password='Pass1234!')
        self.student_unallocated = StudentProfile.objects.create(user=self.user_unallocated, current_room=None)

    def test_reject_request_if_unallocated(self):
        """Requester without an allocated current room cannot request swaps."""
        form = SwapRequestCreateForm(data={'target_room': self.room_m2.id}, user=self.user_unallocated)
        self.assertFalse(form.is_valid())
        self.assertIn("You must have an allocated room before requesting a swap.", form.errors['target_room'][0])

    def test_reject_self_swap(self):
        """Requester cannot request their own currently allocated room."""
        form = SwapRequestCreateForm(data={'target_room': self.room_m1.id}, user=self.user1)
        self.assertFalse(form.is_valid())
        self.assertIn("You cannot request a swap to your own current room.", form.errors['target_room'][0])

    def test_enforce_gender_restriction_rule(self):
        """Requester in male-only block cannot request a room in female-only block."""
        form = SwapRequestCreateForm(data={'target_room': self.room_f1.id}, user=self.user1)
        self.assertFalse(form.is_valid())
        self.assertIn("Gender policy mismatch", form.errors['target_room'][0])

    def test_prevent_duplicate_pending_request(self):
        """Duplicate pending swap request to the same target room is rejected."""
        SwapRequest.objects.create(
            requester=self.student1,
            target_room=self.room_m2,
            status=SwapRequest.Status.PENDING,
        )
        form = SwapRequestCreateForm(data={'target_room': self.room_m2.id}, user=self.user1)
        self.assertFalse(form.is_valid())
        self.assertIn("already have an active pending swap request", form.errors['target_room'][0])

    def test_valid_swap_request_creation(self):
        """Valid target room passes validation."""
        form = SwapRequestCreateForm(data={'target_room': self.room_m2.id}, user=self.user1)
        self.assertTrue(form.is_valid(), form.errors)


class PairwiseSwapExecutionTests(TestCase):
    def setUp(self):
        self.block = HostelBlock.objects.create(name='Block A', gender_restriction='C')
        self.room_a = Room.objects.create(block=self.block, room_number='101', capacity=1)
        self.room_b = Room.objects.create(block=self.block, room_number='102', capacity=1)

        self.user_a = User.objects.create_user(username='student_a', password='Pass1234!')
        self.student_a = StudentProfile.objects.create(user=self.user_a, current_room=self.room_a)

        self.user_b = User.objects.create_user(username='student_b', password='Pass1234!')
        self.student_b = StudentProfile.objects.create(user=self.user_b, current_room=self.room_b)

        # Mutual pending requests: A wants Room B, B wants Room A
        self.swap_a = SwapRequest.objects.create(
            requester=self.student_a,
            target_room=self.room_b,
            status=SwapRequest.Status.PENDING,
        )
        self.swap_b = SwapRequest.objects.create(
            requester=self.student_b,
            target_room=self.room_a,
            status=SwapRequest.Status.PENDING,
        )

        self.client = Client()
        self.client.login(username='student_a', password='Pass1234!')

    def test_pairwise_swap_detected_and_executed_atomically(self):
        """Test pairwise match is visible and execution atomically reallocates both students."""
        # 1. Verify swap matches view displays the pair
        matches_url = reverse('swaps:matches')
        response = self.client.get(matches_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['pairwise_matches']), 1)

        # 2. Execute swap
        exec_url = reverse('swaps:execute', kwargs={'swap_id': self.swap_a.id})
        exec_response = self.client.post(exec_url, follow=True)
        self.assertEqual(exec_response.status_code, 200)

        # 3. Refresh from DB and verify room allocations swapped
        self.student_a.refresh_from_db()
        self.student_b.refresh_from_db()
        self.swap_a.refresh_from_db()
        self.swap_b.refresh_from_db()

        self.assertEqual(self.student_a.current_room, self.room_b)
        self.assertEqual(self.student_b.current_room, self.room_a)
        self.assertEqual(self.swap_a.status, SwapRequest.Status.COMPLETED)
        self.assertEqual(self.swap_b.status, SwapRequest.Status.COMPLETED)


class CircularSwapExecutionTests(TestCase):
    def setUp(self):
        self.block = HostelBlock.objects.create(name='Block C', gender_restriction='C')
        self.room_1 = Room.objects.create(block=self.block, room_number='301', capacity=1)
        self.room_2 = Room.objects.create(block=self.block, room_number='302', capacity=1)
        self.room_3 = Room.objects.create(block=self.block, room_number='303', capacity=1)

        self.u1 = User.objects.create_user(username='student_1', password='Pass1234!')
        self.s1 = StudentProfile.objects.create(user=self.u1, current_room=self.room_1)

        self.u2 = User.objects.create_user(username='student_2', password='Pass1234!')
        self.s2 = StudentProfile.objects.create(user=self.u2, current_room=self.room_2)

        self.u3 = User.objects.create_user(username='student_3', password='Pass1234!')
        self.s3 = StudentProfile.objects.create(user=self.u3, current_room=self.room_3)

        # 3-Party Cycle: s1 wants room_2, s2 wants room_3, s3 wants room_1
        self.swap_12 = SwapRequest.objects.create(
            requester=self.s1, target_room=self.room_2, status=SwapRequest.Status.PENDING
        )
        self.swap_23 = SwapRequest.objects.create(
            requester=self.s2, target_room=self.room_3, status=SwapRequest.Status.PENDING
        )
        self.swap_31 = SwapRequest.objects.create(
            requester=self.s3, target_room=self.room_1, status=SwapRequest.Status.PENDING
        )

        self.client = Client()
        self.client.login(username='student_1', password='Pass1234!')

    def test_3_party_circular_swap_detection_and_simultaneous_reallocation(self):
        """Test 3-party circular swap cycle detection and simultaneous 3-way reallocation."""
        # 1. Verify cycle is detected
        matches_url = reverse('swaps:matches')
        response = self.client.get(matches_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['circular_matches']), 1)

        # 2. Execute the circular swap
        exec_url = reverse('swaps:execute', kwargs={'swap_id': self.swap_12.id})
        exec_response = self.client.post(exec_url, follow=True)
        self.assertEqual(exec_response.status_code, 200)

        # 3. Refresh student profiles & swap requests
        self.s1.refresh_from_db()
        self.s2.refresh_from_db()
        self.s3.refresh_from_db()
        self.swap_12.refresh_from_db()
        self.swap_23.refresh_from_db()
        self.swap_31.refresh_from_db()

        # Check cyclic reallocation: s1 -> room 2, s2 -> room 3, s3 -> room 1
        self.assertEqual(self.s1.current_room, self.room_2)
        self.assertEqual(self.s2.current_room, self.room_3)
        self.assertEqual(self.s3.current_room, self.room_1)

        # All 3 swap requests must be COMPLETED
        self.assertEqual(self.swap_12.status, SwapRequest.Status.COMPLETED)
        self.assertEqual(self.swap_23.status, SwapRequest.Status.COMPLETED)
        self.assertEqual(self.swap_31.status, SwapRequest.Status.COMPLETED)
