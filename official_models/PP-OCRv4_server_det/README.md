---
license: apache-2.0
library_name: PaddleOCR
language:
- en
- zh
pipeline_tag: image-to-text
tags:
- OCR
- PaddlePaddle
- PaddleOCR
- textline_detection
---

# PP-OCRv4_server_det

## Introduction

PP-OCRv4_server_det is one of the PP-OCRv4_det series models, a set of text detection models developed by the PaddleOCR team. This server-side text detection model offers higher accuracy and is suitable for deployment on high-performance servers. Its key accuracy metrics are as follows:

| Handwritten Chinese | Handwritten English | Printed Chinese | Printed English | Traditional Chinese | Ancient Text | Japanese | General Scenario | Pinyin | Rotation | Distortion | Artistic Text | Average | 
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.706 | 0.249 | 0.888 | 0.690	| 0.759 | 0.473 | 0.685	 | 0.715 | 0.542 | 0.366 | 0.775 | 0.583 | 0.662 |

## Quick Start

### Installation

1. PaddlePaddle

Please refer to the following commands to install PaddlePaddle using pip:

```bash
# for CUDA11.8
python -m pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu118/

# for CUDA12.6
python -m pip install paddlepaddle-gpu==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/

# for CPU
python -m pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```

For details about PaddlePaddle installation, please refer to the [PaddlePaddle official website](https://www.paddlepaddle.org.cn/en/install/quick).

2. PaddleOCR

Install the latest version of the PaddleOCR inference package from PyPI:

```bash
python -m pip install paddleocr
```

### Model Usage

You can quickly experience the functionality with a single command:

```bash
paddleocr text_detection \
    --model_name PP-OCRv4_server_det \
    -i https://cdn-uploads.huggingface.co/production/uploads/681c1ecd9539bdde5ae1733c/3ul2Rq4Sk5Cn-l69D695U.png
```

You can also integrate the model inference of the text detection module into your project. Before running the following code, please download the sample image to your local machine.

```python
from paddleocr import TextDetection
model = TextDetection(model_name="PP-OCRv4_server_det")
output = model.predict(input="3ul2Rq4Sk5Cn-l69D695U.png", batch_size=1)
for res in output:
    res.print()
    res.save_to_img(save_path="./output/")
    res.save_to_json(save_path="./output/res.json")
```

After running, the obtained result is as follows:

```json
{'res': {'input_path': '/root/.paddlex/predict_input/3ul2Rq4Sk5Cn-l69D695U.png', 'page_index': None, 'dt_polys': array([[[ 627, 1432],
        ...,
        [ 627, 1449]],

       ...,

       [[ 354,  106],
        ...,
        [ 354,  127]]], dtype=int16), 'dt_scores': [0.9421815230284514, 0.8528662776681952, ..., 0.8209321007152185]}}
```

The visualized image is as follows:

![image/jpeg](https://cdn-uploads.huggingface.co/production/uploads/681c1ecd9539bdde5ae1733c/y1dsK4yO1V0pvqDN_VlMY.jpeg)

For details about usage command and descriptions of parameters, please refer to the [Document](https://paddlepaddle.github.io/PaddleOCR/latest/en/version3.x/module_usage/text_detection.html#iii-quick-start).

### Pipeline Usage

The ability of a single model is limited. But the pipeline consists of several models can provide more capacity to resolve difficult problems in real-world scenarios.

#### PP-OCRv4

The general OCR pipeline is used to solve text recognition tasks by extracting text information from images and outputting it in text form. And there are 5 modules in the pipeline: 
* Document Image Orientation Classification Module (Optional)
* Text Image Unwarping Module (Optional)
* Text Line Orientation Classification Module (Optional)
* Text Detection Module
* Text Recognition Module

Run a single command to quickly experience the OCR pipeline:

```bash
paddleocr ocr -i https://cdn-uploads.huggingface.co/production/uploads/681c1ecd9539bdde5ae1733c/3ul2Rq4Sk5Cn-l69D695U.png \
    --text_detection_model_name PP-OCRv4_server_det \
    --text_recognition_model_name PP-OCRv4_server_rec \
    --use_doc_orientation_classify False \
    --use_doc_unwarping False \
    --use_textline_orientation False \
    --save_path ./output \
    --device gpu:0 
```

Results are printed to the terminal:

```json
{'res': {'input_path': '/root/.paddlex/predict_input/3ul2Rq4Sk5Cn-l69D695U.png', 'page_index': None, 'model_settings': {'use_doc_preprocessor': True, 'use_textline_orientation': False}, 'doc_preprocessor_res': {'input_path': None, 'page_index': None, 'model_settings': {'use_doc_orientation_classify': False, 'use_doc_unwarping': False}, 'angle': -1}, 'dt_polys': array([[[ 355,  109],
        ...,
        [ 355,  126]],

       ...,

       [[ 631, 1431],
        ...,
        [ 631, 1450]]], dtype=int16), 'text_det_params': {'limit_side_len': 64, 'limit_type': 'min', 'thresh': 0.3, 'max_side_limit': 4000, 'box_thresh': 0.6, 'unclip_ratio': 1.5}, 'text_type': 'general', 'textline_orientation_angles': array([-1, ..., -1]), 'text_rec_score_thresh': 0.0, 'rec_texts': ['AlgorithmsfortheMarkovEntropyDecomposition', 'AndrewJ.FerrisandDavidPoulin', 'DepartementdePhysique,UniversitedeSherbrooke，Quebec,JlK2Rl，Canada', '（Dated:October31，2018）', 'TheMarkoventropydecomposition', '(MED)is a recently-proposed, cluster-based simulation method for fi-', 'nite temperature quantum systems with arbitrary geometry. In this p', 'paper,wedetail numerical algorithms for', 'performing the required steps of the MED,principally solving a minimization problem with a', 'preconditioned', 'astea1ocrtratnrtpccc', "Newton's", 'algorithm,as well as how to extract global susceptibilities and thermal responses.', 'Wedemonstrate', 'the power of the method with the spin-l/2 XXZ model on the 2D squarelattice, including the extraction of', 'critical points and details of each phase. Although the method shares some qualitative similarities with exact-', 'diagonalization,we show the MED is both more accurate and significantly more flexible.', 'PACSnumbers:05.10.-a, 02.50.Ng,03.67.-a,74.40.Kb', 'I.INTRODUCTION', 'This approximation becomes exact in the case of a 1D', 'quan-', 'tum（orclassical)', 'Markov chain', '[10],and leads to an', 'expo-', 'Although', 'the', 'equations', 'governing', 'quantum many-body', 'nentialreduction', '1 of cost for exact entropy calculations when', 'systems are', 'simplet', 'writedown，findin', 'solutions', 'sforthe', 'the global density matrix is a higher-dimensional Markov net-', 'majority', 'of', 'systems', 'remains incredibly', 'difficult.', 'Modern', 'workstate', '[12,13].', 'physics finds itself in need of new', 'tools to compute the emer-', 'The second approximation used in the MED approach is', 'gentbehavior of large, many-body', 'ysystems.', 'related to the V-representibility problem. Given a set of lo-', 'Therehasbeen', 'greatvariety', 'r oftools developed to tackle', 'calbutoverlapping', 'reduced density', 'matrices{pi}，it is avery', 'many-bodyproblems', 's,butin', 'general,large', '2D', 'and3D', 'quan-', 'challenging', 'problemto determinei', 'ifthereexists', 'globalden-', 'tum', 'systems', 'remain', 'hard', 'deal', 'with.', 'Most', 'systems', 'are', 'sity operator which is positive semi-definite and whose partial', 'thought to be non-integrable, so exact analytic solutions are', 'trace agrees', 'with', 'each', 'p.This', 'problemisQMA-hard', '(the', 'notusually expected.Direct numerical diagonalization canbe', 'quantum analogue of NP)', '[14，', '151.', 'and is hopelessly', 'diffi-', 'performedforrelatively', 'small', 'wstems', '-howevertheemer-', 'cultto', 'enforce.', 'Thus', 'the', 'second', 'pproximationemployed', 'gentbehaviorofas', 'ystem in thethermodynamiclimitmaybe', 'involves ignoringglobal consistency', 'with a', 'positive', 'opera-', 'difficult to extract, especially in s', 'ystemswithlarge', 'correlation', 'tor,while', 'requiring', 'localconsistenc', 'on any overlapping re-', 'lengths.MonteCarlo', 'approaches are technically', '/exact(upto', 'gionsbetween thep.Atthezero-temperaturelimit,theMED', 'sampling', 'error)，but', 'suffer', 'fromthe', 'so-called', 'ign', 'problem', 'approach becomes analogous to the', 'ariationalnth-orderre-', '111', 'for fermionic, frustrated, or dynamical problems. Thus', 'weare', 'duceddensity', 'matrix', 'approach,', 'where', 'positivity is enforced', 'limitedto', 'search for clever', ' approximations to solve the ma-', 'on all reduced density', 'matrices of size', '[16-18].', ' jority of many-body problems.', 'The MED approach is an extremely flexible cluster method,', 'Overthe', 'pastcentury', 'hundredsof such', 'approximations', 'applicable to both translationally', 'y invariant systems of any di-', 'havebeen', 'proposed,', ' and we will mention just a few notable', 'mension in the thermodynamic limit.', 'as well asfinite', 'ystems', 'examples', 'applicable', 'quantum lattice', 'odels.Mean-field', 'or systems', 'without translational invariance （e.g.', 'disordered', 'theory', 'is simple and frequently', 'arrives', 'at the correct', 'quali-', 'lattices,', 'or harmonically', 'trappedatomsin', 'optical lattices).', 'tative description,but', 'often fails', 'swhen', 'correlations', 'are im-', 'Thefreeenergygivenby', 'MEDis', 'guaranteed to lower', 'bound', 'portant. Density-matrix renormalisation', 'group (DMRG)[1]', 'the true free', 'energy', 'which in turn lower-bounds the', 'ground', 'is efficient and extremely', 'accurate at solving', '1D', 'problems,', 'stateenergy', '—thus', 'providing a natural complement to varia-', 'butthe computational cost', 'grows exponentially', 'ywithsystem', 'tionalapproacheswhich upper-boundthe', 'ground state energy.', 'size in two- or higher-dimensions', '[2,3].', 'Related tensor-', 'The ability to provide a rigorous', 's ground-stateenergywindow', 'networktechniquesdesigned for2D', 'ystemsarestill intheir', 'is apowerful validation tool, creating', 'averycompellingrea-', 'infancy [4-6]. Series-expansion methods', '7', 'canbe success-', 'son to use this approach.', 'ful, but may diverge', 'orotherwise converge', 'eslowly,obscuring', 'In this paper we paper we present a pedagogical introduc-', 'thestatein', '1certain', 'regimes. There exist', 'variety', 'of cluster-', 'tion toMED, includingnumericalimplementation issues and', 'based techniques', 'such as', 'dynamical-mean-field theory[8]', 'applications', 'to 2D quantum lattice', 'models in the thermody-', 'anddensity', '7-matrix', 'embedding[9].', 'namiclimit.', 'In Sec.II,we', 'give a brief derivation', 'ofthe', 'Herewe', 'discuss the so-called Markov entropy decompo-', 'Markov entropy decomposition.', 'SectionIlloutlinesarobust', 'sition (MED),recently', 'proposedby', 'Poulin&Hastings', '[10]', 'numerical strategy for', 'optimizing', 'the clusters that make up', '(andanalogous to a slightly', 'earlier', ' classical algorithm', '[11])', 'thedecomposition.', 'InSec.IVw', 'show how we can extend', 'This is', 'a self-consistent', 'cluster method for finite temperature', 'thesealgorithmsto', 'extract non-trivial', 'information,suchas', 'systems that takes advantage of an ', 'approximationofthe（von', 'specific heat and susceptibilities.We present an application of', 'Neumann)entropy.', 'In[10]，itwas', 'shown that the entropy', 'the method to the spin-1/2 XXZmodel on a 2D squarelattice', 'per site can be rigorously upper bounded using only local in-', 'in Sec.V,describing how to characterize the phase diagram', 'formation—alocal.reduceddensity', 'matrix onN sites,say.', 'and determine critical points, before concluding in Sec.VI.'], 'rec_scores': array([0.98928159, ..., 0.98077077]), 'rec_polys': array([[[ 355,  109],
        ...,
        [ 355,  126]],

       ...,

       [[ 631, 1431],
        ...,
        [ 631, 1450]]], dtype=int16), 'rec_boxes': array([[ 355, ...,  126],
       ...,
       [ 631, ..., 1450]], dtype=int16)}}
```

If save_path is specified, the visualization results will be saved under `save_path`. The visualization output is shown below:

![image/jpeg](https://cdn-uploads.huggingface.co/production/uploads/681c1ecd9539bdde5ae1733c/drL5DSiarbdfIkN92E2VL.jpeg)

The command-line method is for quick experience. For project integration, also only a few codes are needed as well:

```python
from paddleocr import PaddleOCR  

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv4_server_det",
    text_recognition_model_name="PP-OCRv4_server_rec",
    use_doc_orientation_classify=False, # Disables document orientation classification model via this parameter
    use_doc_unwarping=False, # Disables text image rectification model via this parameter
    use_textline_orientation=False, # Disables text line orientation classification model via this parameter
)
result = ocr.predict("./general_ocr.png")  
for res in result:  
    res.print()  
    res.save_to_img("output")  
    res.save_to_json("output")
```

For details about usage command and descriptions of parameters, please refer to the [Document](https://paddlepaddle.github.io/PaddleOCR/latest/en/version3.x/pipeline_usage/OCR.html#2-quick-start).


## Links

[PaddleOCR Repo](https://github.com/paddlepaddle/paddleocr)

[PaddleOCR Documentation](https://paddlepaddle.github.io/PaddleOCR/latest/en/index.html)
