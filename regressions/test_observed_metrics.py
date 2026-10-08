"""Admitted metrics use actual accepted decisions, not expected class totals."""
import copy
import unittest
from evaluate import proposed_metrics

class ObservedMetricsTests(unittest.TestCase):
    def setUp(self):
        self.rows=[{'expected_kind':kind,'expected_decision':decision,
                    'producer_decision':decision,'checker_accepted':True}
                   for kind,decision in [('legal','equivalent'),('legal','equivalent'),
                                         ('different','different'),('different','different'),
                                         ('rejected','out-of-language')]]

    def test_same_admitted_population(self):
        m=proposed_metrics(self.rows)
        self.assertEqual((m['eligible_pairs'],m['true_positive'],m['true_negative']), (4,2,2))
        self.assertEqual((m['accuracy'],m['three_way_accuracy']), (1.0,1.0))

    def test_incorrect_admitted_decision_is_counted(self):
        self.rows[0]['producer_decision']='different'
        m=proposed_metrics(self.rows)
        self.assertEqual((m['true_positive'],m['false_negative'],m['true_negative']), (1,1,2))
        self.assertEqual(m['accuracy'],.75)

    def test_rejected_certificate_is_abstention(self):
        self.rows[0]['checker_accepted']=False
        m=proposed_metrics(self.rows)
        self.assertEqual((m['true_positive'],m['false_negative'],m['abstentions']), (1,0,1))
        self.assertEqual(m['accuracy'],.75)
        self.assertEqual(m['positive_recall'],.5)

    def test_out_of_language_failure_does_not_change_admitted_metrics(self):
        self.rows[-1]['checker_accepted']=False
        m=proposed_metrics(self.rows)
        self.assertEqual(m['accuracy'],1.0)
        self.assertEqual(m['three_way_accuracy'],.8)
        self.assertEqual(m['abstentions'],0)

    def test_no_verdict_on_admitted_negative_is_not_true_negative(self):
        self.rows[2]['producer_decision']='out-of-language'
        original=copy.deepcopy(self.rows)
        m=proposed_metrics(self.rows)
        self.assertEqual((m['true_negative'],m['false_positive'],m['abstentions']), (1,0,1))
        self.assertEqual(m['negative_recall'],.5)
        self.assertEqual(self.rows,original)

if __name__=='__main__':unittest.main()
