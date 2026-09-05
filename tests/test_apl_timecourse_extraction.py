"""Run with bundled PDF Python: unittest tests.test_apl_timecourse_extraction."""
import unittest
import numpy as np
from scripts.extract_apl_timecourses import polygon_points,section,exact_section


class TraceGeometryTests(unittest.TestCase):
    def test_rectangle_and_known_cubic(self):
        paths=[([('m',(0,0)),('l',(1,0)),('l',(1,2)),('l',(0,2)),('h',)],lambda x:0.),
               ([('m',(0,0)),('c',(1/3,0),(2/3,0),(1,1)),('l',(1,2)),('l',(0,2)),('h',)],lambda x:x**3)]
        for path,lower in paths:
            for x in [.1,.3,.7,.9]:
                expected=[lower(x),2.]
                np.testing.assert_allclose(exact_section(path,x),expected,rtol=0,atol=1e-12)
                np.testing.assert_allclose(section(polygon_points(path,32),x),expected,rtol=0,atol=.001)

    def test_declared_decimal_grid_includes_summary_endpoints(self):
        t=np.round(np.arange(-4.5,14.501,.1),10)
        baseline=t[(t>=-4)&(t<=-1)];post=t[(t>=0)&(t<=12)]
        self.assertEqual(len(baseline),31);self.assertEqual(len(post),121)
        np.testing.assert_array_equal([baseline[0],baseline[-1],post[0],post[-1]],[-4,-1,0,12])


if __name__=='__main__':unittest.main()
