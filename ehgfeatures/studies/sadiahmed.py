from smote_variants import ADASYN, OversamplingClassifier

from sklearn.svm import SVC
from sklearn.model_selection import StratifiedKFold, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

import numpy as np
import pandas as pd

import pyswarms as ps

import json

from collections import Counter

sadiahmed_features= ['FeaturesSadiAhmed_emd_3_n_peaks_ch1',
                        'FeaturesSadiAhmed_emd_3_fwh_peak_freq_ch1',
                        'FeaturesSadiAhmed_emd_3_gap_ch1',
                        'FeaturesSadiAhmed_emd_6_n_peaks_ch1',
                        'FeaturesSadiAhmed_emd_6_med_freq_ch1',
                        'FeaturesSadiAhmed_emd_6_fwh_peak_power_ch1',
                        'FeaturesSadiAhmed_emd_6_fwl_peak_power_ch1',
                        'FeaturesSadiAhmed_emd_3_n_peaks_ch2',
                        'FeaturesSadiAhmed_emd_3_fwh_peak_freq_ch2',
                        'FeaturesSadiAhmed_emd_3_gap_ch2',
                        'FeaturesSadiAhmed_emd_6_n_peaks_ch2',
                        'FeaturesSadiAhmed_emd_6_med_freq_ch2',
                        'FeaturesSadiAhmed_emd_6_fwh_peak_power_ch2',
                        'FeaturesSadiAhmed_emd_6_fwl_peak_power_ch2',
                        'FeaturesSadiAhmed_emd_3_n_peaks_ch3',
                        'FeaturesSadiAhmed_emd_3_fwh_peak_freq_ch3',
                        'FeaturesSadiAhmed_emd_3_gap_ch3',
                        'FeaturesSadiAhmed_emd_6_n_peaks_ch3',
                        'FeaturesSadiAhmed_emd_6_med_freq_ch3',
                        'FeaturesSadiAhmed_emd_6_fwh_peak_power_ch3',
                        'FeaturesSadiAhmed_emd_6_fwl_peak_power_ch3']

def evaluate(pipeline, X, y, validator):
    preds= np.zeros((len(X), 3))
    for fold_idx, (train_idx, test_idx) in enumerate(validator.split(X, y)):
        X_train, X_test= X.iloc[train_idx, :], X.iloc[test_idx, :]
        y_train, y_test= y.iloc[train_idx], y.iloc[test_idx]

        pipeline.fit(X_train.values, y_train.values)

        preds[test_idx, 0]= fold_idx
        preds[test_idx, 1]= y_test
        preds[test_idx, 2]= pipeline.predict_proba(X_test.values)[:,1]

    preds= pd.DataFrame(preds, columns=['fold', 'label', 'prediction'])

    return preds

def study_sadiahmed(features, target, preprocessing=StandardScaler(), grid=True, random_seed=42, output_file='sadiahmed_results.json'):
    features = features.loc[:,sadiahmed_features+['Rectime', 'Gestation']]
    mask = (features['Rectime'] >= 27) & (features['Rectime'] <= 32)
    features = features.loc[mask, :]
    target = target.loc[mask]
    
    term_ix = np.arange(len(target), dtype=int)[target == 1]
    preterm_ix = np.arange(len(target), dtype=int)[target == 0]

    term_diffs = list(features.iloc[term_ix]['Gestation'] - features.iloc[term_ix]['Rectime'])
    preterm_diffs = list(features.iloc[preterm_ix]['Gestation'] - features.iloc[preterm_ix]['Rectime'])
    
    features = features.drop(['Rectime', 'Gestation'], axis=1)

    # These indices seem to best resemble the reported mean and stddev...
    term_sample = list(term_ix[np.argsort(term_diffs)[10:25]])
    preterm_sample = list(preterm_ix[np.argsort(preterm_diffs)[2:17]])

    features = features.iloc[term_sample + preterm_sample, :]
    target = target.iloc[term_sample + preterm_sample]

    results= {}
    base_classifier= SVC(kernel='linear', random_state=random_seed, probability=True)
    grid_search_params= {'kernel': ['linear'], 'C': [10**i for i in range(-4, 5)], 'probability': [True], 'random_state': [random_seed]}

    # without oversampling
    classifier= base_classifier if not grid else GridSearchCV(base_classifier, grid_search_params, scoring='roc_auc')
    pipeline= classifier if not preprocessing else Pipeline([('preprocessing', preprocessing), ('classifier', classifier)])
    validator= StratifiedKFold(n_splits=10, random_state= random_seed)

    preds= evaluate(pipeline, features, target, validator)
    results['without_oversampling_auc']= roc_auc_score(preds['label'].values, preds['prediction'].values)
    results['without_oversampling_details']= preds.to_dict()

    print('without oversampling: ', results['without_oversampling_auc'])

    # with correct oversampling
    classifier= base_classifier if not grid else GridSearchCV(base_classifier, grid_search_params, scoring='roc_auc')
    classifier= OversamplingClassifier(ADASYN(), classifier)
    pipeline= classifier if not preprocessing else Pipeline([('preprocessing', preprocessing), ('classifier', classifier)])
    validator= StratifiedKFold(n_splits=10, random_state= random_seed)

    preds= evaluate(classifier, features, target, validator)
    results['with_oversampling_auc']= roc_auc_score(preds['label'].values, preds['prediction'].values)
    results['with_oversampling_details']= preds.to_dict()
    print('with oversampling: ', results['with_oversampling_auc'])

    # in-sample evaluation
    classifier= base_classifier
    preds= classifier.fit(features.values, target.values).predict_proba(features.values)[:,1]
    preds= pd.DataFrame({'fold': 0, 'label': target.values, 'prediction': preds})
    results['in_sample_auc']= roc_auc_score(preds['label'].values, preds['prediction'].values)
    results['in_sample_details']= preds.to_dict()
    print('in sample: ', results['in_sample_auc'])

    # with incorrect oversampling
    X, y= ADASYN().sample(features.values, target.values)
    X= pd.DataFrame(X, columns=features.columns)
    y= pd.Series(y)

    classifier= base_classifier if not grid else GridSearchCV(base_classifier, grid_search_params, scoring='roc_auc')
    pipeline= classifier if not preprocessing else Pipeline([('preprocessing', preprocessing), ('classifier', classifier)])
    validator= StratifiedKFold(n_splits=10, random_state= random_seed)

    preds= evaluate(pipeline, X, y, validator)
    results['incorrect_oversampling_auc']= roc_auc_score(preds['label'].values, preds['prediction'].values)
    results['incorrect_oversampling_details']= preds.to_dict()
    print('incorrect oversampling: ', results['incorrect_oversampling_auc'])

    json.dump(results, open(output_file, 'w'))
    return results