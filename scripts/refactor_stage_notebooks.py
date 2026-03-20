import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]


def md(text: str):
    return [line + "\n" for line in dedent(text).strip("\n").splitlines()]


def code(text: str):
    return [line + "\n" for line in dedent(text).rstrip("\n").splitlines()]


def clear_outputs(nb):
    for cell in nb["cells"]:
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None


def update_stage1():
    path = ROOT / "notebooks" / "5.1_modeling_stage1.ipynb"
    nb = json.loads(path.read_text())
    clear_outputs(nb)

    nb["cells"][10]["source"] = code(
        """
        # Define streamlined global baseline models (10-class direct classification)
        n_classes = y.nunique()

        global_models = {
            'Logistic Regression': LogisticRegression(
                max_iter=3000,
                class_weight='balanced',
                random_state=42
            ),
            'Random Forest': RandomForestClassifier(
                n_estimators=250,
                max_depth=12,
                class_weight='balanced',
                random_state=42,
                n_jobs=-1
            ),
            'XGBoost': XGBClassifier(
                n_estimators=220,
                max_depth=6,
                learning_rate=0.08,
                objective='multi:softprob',
                num_class=n_classes,
                eval_metric='mlogloss',
                random_state=42,
                n_jobs=-1
            ),
        }

        # Hierarchical definitions
        LEVEL_TO_TIERS = {
            0: [0, 1, 2, 3],      # Low: Improve, Stable, MildRise, Jumper
            1: [4, 5, 6],         # Mid: Improve, Stable, Escalate
            2: [7, 8, 9],         # High: Improve, Stable, Escalate
        }

        LEVEL_NAMES = {0: 'Low', 1: 'Mid', 2: 'High'}

        LEVEL_LOCAL_CLASS_NAMES = {
            0: {0: 'Improve', 1: 'Stable', 2: 'MildRise', 3: 'Jumper'},
            1: {0: 'Improve', 1: 'Stable', 2: 'Escalate'},
            2: {0: 'Improve', 1: 'Stable', 2: 'Escalate'},
        }

        TIER_TO_LOCAL = {
            lvl: {tier: i for i, tier in enumerate(tiers)}
            for lvl, tiers in LEVEL_TO_TIERS.items()
        }
        LOCAL_TO_TIER = {
            lvl: {i: tier for i, tier in enumerate(tiers)}
            for lvl, tiers in LEVEL_TO_TIERS.items()
        }

        print(f"Global models to benchmark: {list(global_models.keys())}")
        print("Hierarchical route: level-known + level-specific direction RandomForest")
        """
    )

    nb["cells"][12]["source"] = md(
        """
        ### Interpretation: Benchmark and Selection

        **What this benchmark is answering**

        We are not asking whether Stage 1 can perfectly predict all 10 tiers. We are asking whether Year 1 information contains **usable transition signal beyond baseline cost**, and whether that signal is strong enough to support Stage 2 routing.

        **What the results mean in practice**

        - The selected hierarchical pipeline is kept because it is nearly tied with the best global model on macro-F1, while being easier to explain in healthcare terms: patients stay within their observed Year 1 cost level, and the model focuses on the harder problem of **direction of movement**.
        - The controlled ablation is the key diagnostic. It shows how much of Stage 1 comes from `COST_Y1_ADJ` alone and how much incremental value comes from utilization, chronic burden, medication complexity, and engineered features.
        - If the full model beats the cost-only model, that gap is the evidence that we found predictors **outside Y1 cost persistence**. Those non-cost predictors matter more for the report than squeezing a few extra points from threshold tuning.

        **How to read the benchmark table**

        - `F1 (Macro)` is the main fairness-style score across all 10 tiers.
        - `Direction_F1_Macro` is more important clinically because it asks whether we can distinguish **improve / stable / escalate**.
        - `Cost-only / Full F1 ratio` tells us whether the model is mostly reusing last year's spending level or learning additional clinical/utilization signal.
        """
    )

    nb["cells"][15]["source"] = md(
        """
        ## 5.1A Stage 1 Policy Screening: Keep Only Reportable Operating Points

        The original notebook evaluated many policy variants. That is useful during development, but it is not useful in the report if several variants are non-actionable or visually indistinguishable.

        This revised section keeps a simple narrative:

        - `Baseline_Selected`: the best overall Stage 1 classifier for full 10-class routing.
        - `Hier_Targeted`: a recall-tilted hierarchical sensitivity test using business-cost weighting and targeted slice reweighting.
        - `Global_Calibrated`: a calibrated global policy used only as an **escalation-screening sensitivity analysis**.

        **Why we are dropping the rest from the narrative**

        - We do not keep variants whose rare-class recall/precision trade-off is too extreme to guide action.
        - We do not keep multiple policy variants that tell the same story with slightly different thresholds.
        - We do not use the low-recall baseline rare-class performance as an operational recommendation. It stays only as a benchmark reference.

        **Decision rule for downstream use**

        - Stage 2 routing keeps the **baseline hard class probabilities** as the default input, because overall routing quality matters more than forcing a threshold policy that degrades global classification.
        - If the team wants an operational screening view for `High_Escalate`, use the retained calibrated screening scenario as a sensitivity analysis, not as the default routing rule.
        """
    )

    nb["cells"][16]["source"] = code(
        """
        # Stage 1 policy screening: retain only reportable operating points

        FOCUS_CLASSES = [3, 9]  # Low_Jumper, High_Escalate
        DEFAULT_POLICY_CONSTRAINTS = {
            'Low_Jumper_Precision': 0.30,
            'High_Escalate_Recall': 0.55,
            'Abstain_Rate': 0.15,
        }

        POLICY_SCENARIOS = {
            'Balanced': DEFAULT_POLICY_CONSTRAINTS,
            'Conservative': {
                'Low_Jumper_Precision': 0.36,
                'High_Escalate_Recall': 0.50,
                'Abstain_Rate': 0.15,
            },
            'Aggressive': {
                'Low_Jumper_Precision': 0.22,
                'High_Escalate_Recall': 0.62,
                'Abstain_Rate': 0.20,
            },
        }

        LEVEL_MAP = {
            0: 'Low', 1: 'Low', 2: 'Low', 3: 'Low',
            4: 'Mid', 5: 'Mid', 6: 'Mid',
            7: 'High', 8: 'High', 9: 'High',
        }
        DIRECTION3_MAP = {
            0: 'Improve', 1: 'Stable', 2: 'Escalate', 3: 'Escalate',
            4: 'Improve', 5: 'Stable', 6: 'Escalate',
            7: 'Improve', 8: 'Stable', 9: 'Escalate',
        }


        def precision_recall_for_class(y_true_s, y_pred_s, cls):
            y_true_bin = (y_true_s == cls)
            y_pred_bin = (y_pred_s == cls)
            tp = int((y_true_bin & y_pred_bin).sum())
            fp = int((~y_true_bin & y_pred_bin).sum())
            fn = int((y_true_bin & ~y_pred_bin).sum())
            precision = tp / max(tp + fp, 1)
            recall = tp / max(tp + fn, 1)
            return precision, recall


        def multiclass_ece(y_true_arr, proba, n_bins=15):
            y_true_arr = np.asarray(y_true_arr)
            proba = np.asarray(proba)
            pred = proba.argmax(axis=1)
            conf = proba.max(axis=1)
            corr = (pred == y_true_arr).astype(float)
            bins = np.linspace(0.0, 1.0, n_bins + 1)
            ece = 0.0
            for i in range(n_bins):
                lo, hi = bins[i], bins[i + 1]
                m = (conf >= lo) & (conf < hi if i < n_bins - 1 else conf <= hi)
                if m.sum() == 0:
                    continue
                ece += np.abs(corr[m].mean() - conf[m].mean()) * (m.sum() / len(y_true_arr))
            return float(ece)


        def apply_decision_policy(proba, thresholds, tau_maxprob, tau_margin):
            hard_pred = proba.argmax(axis=1)

            scaled = proba.copy()
            for cls, thr in thresholds.items():
                scaled[:, cls] = scaled[:, cls] / max(thr, 1e-6)

            policy_raw = scaled.argmax(axis=1)

            sorted_prob = np.sort(proba, axis=1)
            max_prob = sorted_prob[:, -1]
            margin = sorted_prob[:, -1] - sorted_prob[:, -2]

            review_flag = (max_prob < tau_maxprob) | (margin < tau_margin)
            policy_pred = policy_raw.copy()
            policy_pred[review_flag] = -1
            eval_pred = np.where(review_flag, hard_pred, policy_raw)

            return {
                'hard_pred': hard_pred,
                'policy_pred': policy_pred,
                'eval_pred': eval_pred,
                'review_flag': review_flag.astype(int),
                'max_prob': max_prob,
                'margin': margin,
            }


        def fit_binary_calibrator(x, y_bin, method):
            x = np.asarray(x).reshape(-1)
            y_bin = np.asarray(y_bin).astype(int)
            if np.unique(y_bin).size < 2:
                return None

            if method == 'isotonic':
                model = IsotonicRegression(out_of_bounds='clip')
                model.fit(x, y_bin)
                return model

            if method == 'platt':
                model = LogisticRegression(max_iter=1000, solver='lbfgs')
                model.fit(x.reshape(-1, 1), y_bin)
                return model

            raise ValueError(f'Unknown calibrator: {method}')


        def apply_binary_calibrator(model, x, method):
            x = np.asarray(x).reshape(-1)
            if model is None:
                return x
            if method == 'isotonic':
                return model.predict(x)
            if method == 'platt':
                return model.predict_proba(x.reshape(-1, 1))[:, 1]
            raise ValueError(f'Unknown calibrator: {method}')


        def calibrate_focus_classes(val_proba, y_val, test_proba, focus_classes, method):
            val_cal = val_proba.copy()
            test_cal = test_proba.copy()

            for cls in focus_classes:
                y_bin = (y_val.values == cls).astype(int)
                model = fit_binary_calibrator(val_proba[:, cls], y_bin, method)
                val_cal[:, cls] = apply_binary_calibrator(model, val_proba[:, cls], method)
                test_cal[:, cls] = apply_binary_calibrator(model, test_proba[:, cls], method)

            val_cal = val_cal / np.clip(val_cal.sum(axis=1, keepdims=True), 1e-12, None)
            test_cal = test_cal / np.clip(test_cal.sum(axis=1, keepdims=True), 1e-12, None)
            return val_cal, test_cal


        def summarize_prediction_bundle(name, narrative_role, operational_use, y_true_s, policy_out, y_proba_s):
            y_eval = pd.Series(policy_out['eval_pred'], index=y_true_s.index)
            y_hard = pd.Series(policy_out['hard_pred'], index=y_true_s.index)

            row = {
                'Experiment': name,
                'NarrativeRole': narrative_role,
                'OperationalUse': operational_use,
                'Accuracy': accuracy_score(y_true_s, y_eval),
                'F1_Macro_10Class': f1_score(y_true_s, y_eval, average='macro'),
                'F1_Weighted_10Class': f1_score(y_true_s, y_eval, average='weighted'),
            }

            y_true_level = y_true_s.map(LEVEL_MAP)
            y_pred_level = y_eval.map(LEVEL_MAP)
            y_true_dir = y_true_s.map(DIRECTION3_MAP)
            y_pred_dir = y_eval.map(DIRECTION3_MAP)

            row['Level_Acc'] = accuracy_score(y_true_level, y_pred_level)
            row['Level_F1_Macro'] = f1_score(y_true_level, y_pred_level, average='macro')
            row['Direction_Acc'] = accuracy_score(y_true_dir, y_pred_dir)
            row['Direction_F1_Macro'] = f1_score(y_true_dir, y_pred_dir, average='macro')

            for cls, key in [(3, 'Low_Jumper'), (9, 'High_Escalate')]:
                p, r = precision_recall_for_class(y_true_s, y_eval, cls)
                row[f'{key}_Precision'] = p
                row[f'{key}_Recall'] = r

            y_onehot = np.zeros((len(y_true_s), len(CLASS_NAMES)), dtype=float)
            y_onehot[np.arange(len(y_true_s)), y_true_s.values] = 1.0
            row['Brier_Multi'] = np.mean(np.sum((y_proba_s - y_onehot) ** 2, axis=1))
            row['ECE_Multi'] = multiclass_ece(y_true_s.values, y_proba_s)
            row['Abstain_Rate'] = float(policy_out['review_flag'].mean())
            row['Hard_vs_Eval_Agreement'] = float((y_hard.values == y_eval.values).mean())

            row['Low_Jumper_F1'] = (
                2 * row['Low_Jumper_Precision'] * row['Low_Jumper_Recall']
                / max(row['Low_Jumper_Precision'] + row['Low_Jumper_Recall'], 1e-12)
            )
            row['High_Escalate_F1'] = (
                2 * row['High_Escalate_Precision'] * row['High_Escalate_Recall']
                / max(row['High_Escalate_Precision'] + row['High_Escalate_Recall'], 1e-12)
            )
            row['Operationally_Actionable'] = (
                row['High_Escalate_Recall'] >= 0.55
                and row['High_Escalate_Precision'] >= 0.20
                and row['Low_Jumper_Recall'] >= 0.20
            )
            return row


        def optimize_policy(val_proba, y_val, focus_classes, constraints):
            cls_a, cls_b = focus_classes

            thr_a_grid = np.linspace(
                max(np.quantile(val_proba[:, cls_a], 0.55), 1e-4),
                max(np.quantile(val_proba[:, cls_a], 0.985), 0.20),
                10
            )
            thr_b_grid = np.linspace(
                max(np.quantile(val_proba[:, cls_b], 0.55), 1e-4),
                max(np.quantile(val_proba[:, cls_b], 0.985), 0.20),
                10
            )
            tau_max_grid = [0.24, 0.28, 0.32]
            tau_margin_grid = [0.03, 0.05, 0.07]

            best = None
            best_obj = -1e18

            for t_a in thr_a_grid:
                for t_b in thr_b_grid:
                    for tau_max in tau_max_grid:
                        for tau_margin in tau_margin_grid:
                            policy = apply_decision_policy(
                                val_proba,
                                thresholds={cls_a: float(t_a), cls_b: float(t_b)},
                                tau_maxprob=float(tau_max),
                                tau_margin=float(tau_margin),
                            )
                            y_eval = pd.Series(policy['eval_pred'], index=y_val.index)

                            f1_macro = f1_score(y_val, y_eval, average='macro')
                            dir_f1 = f1_score(
                                y_val.map(DIRECTION3_MAP),
                                y_eval.map(DIRECTION3_MAP),
                                average='macro'
                            )
                            p3, r3 = precision_recall_for_class(y_val, y_eval, cls_a)
                            p9, r9 = precision_recall_for_class(y_val, y_eval, cls_b)
                            abstain = float(policy['review_flag'].mean())

                            penalty = 0.0
                            penalty += max(constraints['Low_Jumper_Precision'] - p3, 0.0) * 2.5
                            penalty += max(constraints['High_Escalate_Recall'] - r9, 0.0) * 2.0
                            penalty += max(abstain - constraints['Abstain_Rate'], 0.0) * 1.5

                            obj = 0.90 * f1_macro + 0.70 * dir_f1 + 0.50 * r9 + 0.20 * r3 - 0.60 * abstain - penalty

                            row = {
                                'thresholds': {cls_a: float(t_a), cls_b: float(t_b)},
                                'tau_maxprob': float(tau_max),
                                'tau_margin': float(tau_margin),
                                'low_jumper_precision': float(p3),
                                'low_jumper_recall': float(r3),
                                'high_escalate_precision': float(p9),
                                'high_escalate_recall': float(r9),
                                'abstain_rate': abstain,
                                'objective': float(obj),
                            }
                            if obj > best_obj:
                                best_obj = obj
                                best = row

            return best


        def make_boundary_mask(frame, pct=0.05):
            if 'Y1_BIN' not in frame.columns or 'COST_Y1_ADJ' not in frame.columns:
                return pd.Series(False, index=frame.index)

            bvals = frame['Y1_BIN'].dropna().astype(int)
            uniq = sorted(bvals.unique())
            boundaries = []
            for b in uniq:
                if (b + 1) not in set(uniq):
                    continue
                left = frame.loc[frame['Y1_BIN'] == b, 'COST_Y1_ADJ']
                right = frame.loc[frame['Y1_BIN'] == (b + 1), 'COST_Y1_ADJ']
                if len(left) > 0 and len(right) > 0:
                    boundaries.append((left.max() + right.min()) / 2)

            if len(boundaries) == 0:
                return pd.Series(False, index=frame.index)

            bvals = np.array(boundaries)
            dist = np.min(
                np.abs(frame['COST_Y1_ADJ'].values[:, None] - bvals[None, :])
                / np.clip(bvals[None, :], 1e-6, None),
                axis=1,
            )
            return pd.Series(dist <= pct, index=frame.index)


        def make_corner_masks(frame, y_true):
            util_rx = frame['UTIL_RX_Y1'] if 'UTIL_RX_Y1' in frame.columns else pd.Series(0, index=frame.index)
            total_cond = frame['CNT_TOTAL_CONDITIONS'] if 'CNT_TOTAL_CONDITIONS' in frame.columns else pd.Series(0, index=frame.index)
            poly = frame['POLYPHARMACY_FLAG'] if 'POLYPHARMACY_FLAG' in frame.columns else pd.Series(0, index=frame.index)
            dbscan = frame['DBSCAN_CLUSTER'] if 'DBSCAN_CLUSTER' in frame.columns else pd.Series(0, index=frame.index)

            util_total = (
                frame['UTIL_ER_Y1'].fillna(0) + frame['UTIL_IP_Y1'].fillna(0)
                + frame['UTIL_OB_Y1'].fillna(0) + frame['UTIL_RX_Y1'].fillna(0)
            ) if set(['UTIL_ER_Y1', 'UTIL_IP_Y1', 'UTIL_OB_Y1', 'UTIL_RX_Y1']).issubset(frame.columns) else pd.Series(0, index=frame.index)

            masks = {
                'Boundary_Y1Cost_5pct': make_boundary_mask(frame, pct=0.05),
                'DBSCAN_Noise': (dbscan == -1),
                'Polypharmacy': (poly == 1),
                'Sparse_Util_Cond': ((util_rx == 0) & (total_cond <= 1)),
                'Extreme_HighCost_95pct': (
                    frame['COST_Y1_ADJ'] >= frame['COST_Y1_ADJ'].quantile(0.95)
                ) if 'COST_Y1_ADJ' in frame.columns else pd.Series(False, index=frame.index),
                'Zero_Utilization': (util_total == 0),
                'True_Low_Jumper': (y_true == 3),
                'True_High_Escalate': (y_true == 9),
            }
            return masks


        def targeted_sample_weights(frame):
            w = pd.Series(1.0, index=frame.index)
            masks = make_corner_masks(frame, pd.Series(index=frame.index, data=np.zeros(len(frame), dtype=int)))
            for key, mult in [
                ('Boundary_Y1Cost_5pct', 1.25),
                ('DBSCAN_Noise', 1.20),
                ('Polypharmacy', 1.20),
                ('Sparse_Util_Cond', 1.20),
            ]:
                m = masks[key]
                w.loc[m] = w.loc[m] * mult
            return w.clip(upper=2.5)


        tr_sub_idx, va_idx = train_test_split(
            X_train.index,
            test_size=0.25,
            random_state=42,
            stratify=y_train
        )

        X_sub_raw = X_raw.loc[tr_sub_idx].copy()
        X_val_raw = X_raw.loc[va_idx].copy()
        y_sub = y.loc[tr_sub_idx].copy()
        y_val = y.loc[va_idx].copy()

        exp_prep = fit_preprocessor(X_sub_raw)
        X_sub = apply_preprocessor(X_sub_raw, exp_prep)
        X_val = apply_preprocessor(X_val_raw, exp_prep)
        X_test_exp = apply_preprocessor(X_test_raw, exp_prep)

        level_sub = df.loc[tr_sub_idx, 'Y1_LEVEL'].astype(int)
        level_val = df.loc[va_idx, 'Y1_LEVEL'].astype(int)
        level_train = df.loc[X_train.index, 'Y1_LEVEL'].astype(int)
        level_test = df.loc[X_test.index, 'Y1_LEVEL'].astype(int)

        boost_map = {0: {3: 2.8}, 1: {2: 1.9}, 2: {2: 2.2}}


        def build_weighted_direction_model(y_local, lvl):
            counts = y_local.value_counts().to_dict()
            n = len(y_local)
            k = y_local.nunique()
            cw = {int(cls): n / max(k * cnt, 1) for cls, cnt in counts.items()}
            for cls_local, mult in boost_map.get(lvl, {}).items():
                if cls_local in cw:
                    cw[cls_local] = cw[cls_local] * mult
            return RandomForestClassifier(
                n_estimators=340,
                max_depth=13,
                class_weight=cw,
                random_state=42,
                n_jobs=-1,
            )


        def train_hier_models(X_tr_proc, y_tr_s, level_tr_s, raw_frame, targeted=False):
            models = {}
            for lvl, tiers in LEVEL_TO_TIERS.items():
                m = level_tr_s == lvl
                X_l = X_tr_proc.loc[m]
                y_local = y_tr_s.loc[m].map(TIER_TO_LOCAL[lvl]).astype(int)

                if len(X_l) == 0:
                    models[lvl] = {'model': None, 'constant_local': 0, 'tiers': tiers}
                    continue

                if y_local.nunique() <= 1:
                    models[lvl] = {'model': None, 'constant_local': int(y_local.iloc[0]), 'tiers': tiers}
                    continue

                mdl = build_weighted_direction_model(y_local, lvl)
                if targeted:
                    sw = targeted_sample_weights(raw_frame.loc[X_l.index])
                    mdl.fit(X_l, y_local, sample_weight=sw.values)
                else:
                    mdl.fit(X_l, y_local)

                models[lvl] = {'model': mdl, 'constant_local': None, 'tiers': tiers}
            return models


        def predict_hier_models(models, X_proc, level_s):
            proba = np.zeros((len(X_proc), len(CLASS_NAMES)), dtype=float)
            pred = np.full(len(X_proc), -1, dtype=int)

            for lvl, bundle in models.items():
                loc = np.where(level_s.values == lvl)[0]
                if len(loc) == 0:
                    continue

                X_l = X_proc.iloc[loc]
                tiers = bundle['tiers']

                if bundle['model'] is None:
                    local_proba = np.zeros((len(loc), len(tiers)), dtype=float)
                    local_proba[:, bundle['constant_local']] = 1.0
                else:
                    raw = bundle['model'].predict_proba(X_l)
                    local_proba = np.zeros((len(loc), len(tiers)), dtype=float)
                    for k, cls_local in enumerate(bundle['model'].classes_):
                        local_proba[:, int(cls_local)] = raw[:, k]

                for local_i, tier in LOCAL_TO_TIER[lvl].items():
                    proba[loc, tier] = local_proba[:, local_i]

                pred[loc] = np.array([LOCAL_TO_TIER[lvl][int(x)] for x in local_proba.argmax(axis=1)], dtype=int)

            proba = proba / np.clip(proba.sum(axis=1, keepdims=True), 1e-12, None)
            return pred, proba


        experiment_rows = []
        experiment_preds_eval = {}
        experiment_preds_policy = {}
        experiment_review_flags = {}
        experiment_probas = {}
        calibration_rows = []
        policy_rows = []

        baseline_pred_series = pd.Series(y_pred_best, index=y_test.index)
        baseline_proba = y_proba_best.copy()
        baseline_policy_out = {
            'hard_pred': baseline_pred_series.values,
            'policy_pred': baseline_pred_series.values,
            'eval_pred': baseline_pred_series.values,
            'review_flag': np.zeros(len(baseline_pred_series), dtype=int),
            'max_prob': baseline_proba.max(axis=1),
            'margin': np.sort(baseline_proba, axis=1)[:, -1] - np.sort(baseline_proba, axis=1)[:, -2],
        }

        experiment_rows.append(
            summarize_prediction_bundle(
                'Baseline_Selected',
                narrative_role='Overall benchmark for routing',
                operational_use='Use for default Stage 2 routing only',
                y_true_s=y_test,
                policy_out=baseline_policy_out,
                y_proba_s=baseline_proba,
            )
        )
        experiment_preds_eval['Baseline_Selected'] = pd.Series(baseline_policy_out['eval_pred'], index=y_test.index)
        experiment_preds_policy['Baseline_Selected'] = pd.Series(baseline_policy_out['policy_pred'], index=y_test.index)
        experiment_review_flags['Baseline_Selected'] = pd.Series(baseline_policy_out['review_flag'], index=y_test.index)
        experiment_probas['Baseline_Selected'] = baseline_proba

        # Hierarchical targeted sensitivity test
        hier_targeted = train_hier_models(X_train, y_train, level_train, X_train_raw, targeted=True)
        pred_e2, proba_e2 = predict_hier_models(hier_targeted, X_test, level_test)
        e2_out = {
            'hard_pred': pred_e2,
            'policy_pred': pred_e2,
            'eval_pred': pred_e2,
            'review_flag': np.zeros(len(pred_e2), dtype=int),
            'max_prob': proba_e2.max(axis=1),
            'margin': np.sort(proba_e2, axis=1)[:, -1] - np.sort(proba_e2, axis=1)[:, -2],
        }
        experiment_rows.append(
            summarize_prediction_bundle(
                'Hier_Targeted',
                narrative_role='Rare-class sensitivity test',
                operational_use='Do not use as default routing; inspect as recall stress test',
                y_true_s=y_test,
                policy_out=e2_out,
                y_proba_s=proba_e2,
            )
        )
        experiment_preds_eval['Hier_Targeted'] = pd.Series(e2_out['eval_pred'], index=y_test.index)
        experiment_preds_policy['Hier_Targeted'] = pd.Series(e2_out['policy_pred'], index=y_test.index)
        experiment_review_flags['Hier_Targeted'] = pd.Series(e2_out['review_flag'], index=y_test.index)
        experiment_probas['Hier_Targeted'] = proba_e2

        # Calibrated global screening sensitivity test
        if 'XGBoost' in trained_global_models:
            gxgb = trained_global_models['XGBoost']
        else:
            gxgb = trained_global_models[best_global_name]

        gxgb_local = clone(gxgb)
        gxgb_local.fit(X_sub, y_sub)
        val_proba_g = gxgb_local.predict_proba(X_val)
        test_proba_g = gxgb_local.predict_proba(X_test)

        cal_candidates = {}
        for method in ['isotonic', 'platt']:
            val_cal, test_cal = calibrate_focus_classes(val_proba_g, y_val, test_proba_g, FOCUS_CLASSES, method)
            row = {
                'Experiment': 'Global_Calibrated',
                'Calibrator': method,
                'Val_ECE': multiclass_ece(y_val.values, val_cal),
                'Val_Brier_Multi': np.mean(np.sum((np.eye(len(CLASS_NAMES))[y_val.values] - val_cal) ** 2, axis=1)),
                'Val_Direction_F1': f1_score(
                    y_val.map(DIRECTION3_MAP),
                    pd.Series(val_cal.argmax(axis=1), index=y_val.index).map(DIRECTION3_MAP),
                    average='macro'
                ),
            }
            calibration_rows.append(row)
            cal_candidates[method] = {'val': val_cal, 'test': test_cal, 'score': row['Val_ECE'] + 0.20 * row['Val_Brier_Multi']}

        best_method = min(cal_candidates, key=lambda k: cal_candidates[k]['score'])
        val_cal_g = cal_candidates[best_method]['val']
        test_cal_g = cal_candidates[best_method]['test']
        cfg_g = optimize_policy(val_cal_g, y_val, FOCUS_CLASSES, POLICY_SCENARIOS['Balanced'])
        policy_rows.append({
            'Experiment': 'Global_Calibrated',
            'Scenario': 'Balanced',
            'threshold_low_jumper': cfg_g['thresholds'][3],
            'threshold_high_escalate': cfg_g['thresholds'][9],
            'tau_maxprob': cfg_g['tau_maxprob'],
            'tau_margin': cfg_g['tau_margin'],
            'Low_Jumper_Precision_Val': cfg_g['low_jumper_precision'],
            'Low_Jumper_Recall_Val': cfg_g['low_jumper_recall'],
            'High_Escalate_Precision_Val': cfg_g['high_escalate_precision'],
            'High_Escalate_Recall_Val': cfg_g['high_escalate_recall'],
            'Abstain_Rate_Val': cfg_g['abstain_rate'],
            'Calibrator': best_method,
        })

        e4_out = apply_decision_policy(
            test_cal_g,
            cfg_g['thresholds'],
            cfg_g['tau_maxprob'],
            cfg_g['tau_margin']
        )
        experiment_rows.append(
            summarize_prediction_bundle(
                'Global_Calibrated',
                narrative_role='Optional escalation-screening sensitivity test',
                operational_use='Use only if recall for High_Escalate is prioritized over precision',
                y_true_s=y_test,
                policy_out=e4_out,
                y_proba_s=test_cal_g,
            )
        )
        experiment_preds_eval['Global_Calibrated'] = pd.Series(e4_out['eval_pred'], index=y_test.index)
        experiment_preds_policy['Global_Calibrated'] = pd.Series(e4_out['policy_pred'], index=y_test.index)
        experiment_review_flags['Global_Calibrated'] = pd.Series(e4_out['review_flag'], index=y_test.index)
        experiment_probas['Global_Calibrated'] = test_cal_g

        full_exp_df = pd.DataFrame(experiment_rows)
        report_order = ['Baseline_Selected', 'Hier_Targeted', 'Global_Calibrated']
        exp_df = (
            full_exp_df[full_exp_df['Experiment'].isin(report_order)]
            .copy()
            .set_index('Experiment')
            .loc[report_order]
            .reset_index()
        )

        display_cols = [
            'Experiment', 'NarrativeRole', 'Accuracy', 'F1_Macro_10Class', 'Direction_F1_Macro',
            'Low_Jumper_Precision', 'Low_Jumper_Recall', 'High_Escalate_Precision',
            'High_Escalate_Recall', 'Abstain_Rate', 'OperationalUse'
        ]
        print("\\n=== Stage 1 Reportable Operating Points ===")
        display(exp_df[display_cols])

        exp_path = REPORT_DIR / 'tables' / 'stage1_experiment_results.csv'
        exp_df.to_csv(exp_path, index=False)
        print(f"Experiment results saved to: {exp_path}")

        calib_df = pd.DataFrame(calibration_rows)
        calib_df.to_csv(REPORT_DIR / 'tables' / 'stage1_calibration_report.csv', index=False)
        print(f"Calibration report saved to: {REPORT_DIR / 'tables' / 'stage1_calibration_report.csv'}")

        policy_df = pd.DataFrame(policy_rows)
        policy_df.to_csv(REPORT_DIR / 'tables' / 'stage1_threshold_policy.csv', index=False)
        print(f"Threshold policy saved to: {REPORT_DIR / 'tables' / 'stage1_threshold_policy.csv'}")

        operating_cols = [
            'Experiment', 'NarrativeRole', 'F1_Macro_10Class', 'Direction_F1_Macro',
            'Low_Jumper_Precision', 'Low_Jumper_Recall', 'High_Escalate_Precision',
            'High_Escalate_Recall', 'Abstain_Rate', 'Operationally_Actionable'
        ]
        op_df = exp_df[operating_cols].copy()
        op_df.to_csv(REPORT_DIR / 'tables' / 'stage1_operating_points.csv', index=False)
        print(f"Operating points saved to: {REPORT_DIR / 'tables' / 'stage1_operating_points.csv'}")

        print("\\nInterpretation note:")
        print("  - Baseline_Selected is the default routing model because it preserves overall 10-class performance.")
        print("  - Global_Calibrated is kept only as a screening sensitivity test for rare escalation capture.")
        print("  - Hier_Targeted is retained only to show the recall/precision trade-off under aggressive rare-class weighting.")

        # Corner-case suite: compare retained operational screen vs baseline
        print("\\n=== Corner-Case Test Suite ===")
        test_df = df.loc[X_test.index].copy()
        corner_masks = make_corner_masks(test_df, y_test)

        corner_rows = []
        for exp_name in ['Baseline_Selected', 'Hier_Targeted', 'Global_Calibrated']:
            pred_eval_s = experiment_preds_eval[exp_name]
            for case_name, mask in corner_masks.items():
                idx = mask[mask].index
                n = len(idx)
                if n < 30:
                    continue

                y_true_case = y_test.loc[idx]
                y_pred_case = pred_eval_s.loc[idx]

                p3, r3 = precision_recall_for_class(y_true_case, y_pred_case, 3)
                p9, r9 = precision_recall_for_class(y_true_case, y_pred_case, 9)

                corner_rows.append({
                    'Experiment': exp_name,
                    'CornerCase': case_name,
                    'N': n,
                    'Accuracy': accuracy_score(y_true_case, y_pred_case),
                    'F1_Macro_10Class': f1_score(y_true_case, y_pred_case, average='macro') if y_true_case.nunique() > 1 else np.nan,
                    'Direction_F1_Macro': f1_score(y_true_case.map(DIRECTION3_MAP), y_pred_case.map(DIRECTION3_MAP), average='macro') if y_true_case.nunique() > 1 else np.nan,
                    'Low_Jumper_Precision': p3,
                    'Low_Jumper_Recall': r3,
                    'High_Escalate_Precision': p9,
                    'High_Escalate_Recall': r9,
                })

        corner_df = pd.DataFrame(corner_rows).sort_values(['CornerCase', 'Experiment'])
        display(corner_df)
        corner_path = REPORT_DIR / 'tables' / 'stage1_corner_case_results.csv'
        corner_df.to_csv(corner_path, index=False)
        print(f"Corner-case results saved to: {corner_path}")

        rng = np.random.default_rng(42)


        def bootstrap_ci_diff(y_true_s, pred_a_s, pred_b_s, metric_fn, n_boot=200):
            idx = np.arange(len(y_true_s))
            diffs = []
            for _ in range(n_boot):
                bs = rng.choice(idx, size=len(idx), replace=True)
                yb = y_true_s.iloc[bs]
                pa = pred_a_s.iloc[bs]
                pb = pred_b_s.iloc[bs]
                diffs.append(metric_fn(yb, pb) - metric_fn(yb, pa))
            lo, hi = np.quantile(diffs, [0.025, 0.975])
            return float(np.mean(diffs)), float(lo), float(hi)


        def metric_dir_f1(y_true_s, y_pred_s):
            if y_true_s.nunique() <= 1:
                return np.nan
            return f1_score(y_true_s.map(DIRECTION3_MAP), y_pred_s.map(DIRECTION3_MAP), average='macro')


        def metric_highesc_recall(y_true_s, y_pred_s):
            return precision_recall_for_class(y_true_s, y_pred_s, 9)[1]


        base_pred = experiment_preds_eval['Baseline_Selected']
        screen_pred = experiment_preds_eval['Global_Calibrated']

        lift_rows = []
        for case_name, mask in corner_masks.items():
            idx = mask[mask].index
            if len(idx) < 30:
                continue

            y_case = y_test.loc[idx]
            base_case = base_pred.loc[idx]
            screen_case = screen_pred.loc[idx]

            base_dir = metric_dir_f1(y_case, base_case)
            screen_dir = metric_dir_f1(y_case, screen_case)

            d_mean, d_lo, d_hi = bootstrap_ci_diff(
                y_case,
                base_case,
                screen_case,
                metric_fn=metric_dir_f1,
                n_boot=200,
            )

            base_r9 = metric_highesc_recall(y_case, base_case)
            screen_r9 = metric_highesc_recall(y_case, screen_case)

            r9_mean, r9_lo, r9_hi = bootstrap_ci_diff(
                y_case,
                base_case,
                screen_case,
                metric_fn=metric_highesc_recall,
                n_boot=200,
            )

            lift_rows.append({
                'CornerCase': case_name,
                'N': int(len(idx)),
                'ComparedExperiment': 'Global_Calibrated',
                'Baseline_Direction_F1': base_dir,
                'Screening_Direction_F1': screen_dir,
                'Lift_Direction_F1': screen_dir - base_dir if pd.notnull(base_dir) and pd.notnull(screen_dir) else np.nan,
                'Lift_Direction_F1_BootMean': d_mean,
                'Lift_Direction_F1_CI_Low': d_lo,
                'Lift_Direction_F1_CI_High': d_hi,
                'Baseline_HighEsc_Recall': base_r9,
                'Screening_HighEsc_Recall': screen_r9,
                'Lift_HighEsc_Recall': screen_r9 - base_r9,
                'Lift_HighEsc_Recall_BootMean': r9_mean,
                'Lift_HighEsc_Recall_CI_Low': r9_lo,
                'Lift_HighEsc_Recall_CI_High': r9_hi,
            })

        slice_lift_df = pd.DataFrame(lift_rows).sort_values('CornerCase')
        display(slice_lift_df)
        slice_lift_path = REPORT_DIR / 'tables' / 'stage1_slice_lift_table.csv'
        slice_lift_df.to_csv(slice_lift_path, index=False)
        print(f"Slice lift table saved to: {slice_lift_path}")

        # Default OOF routing stays with hard predictions; policy variants are screening diagnostics only.
        SELECTED_POLICY_FOR_OOF = {
            'source_experiment': 'Baseline_Selected_HardOnly',
            'thresholds': {},
            'tau_maxprob': 0.0,
            'tau_margin': 0.0,
        }

        print("\\nSelected policy template for OOF:")
        print(SELECTED_POLICY_FOR_OOF)
        """
    )

    nb["cells"][19]["source"] = md(
        """
        ### Feature Importance Interpretation

        This chart should answer one report question clearly: **what is driving prediction beyond Y1 cost?**

        Read it in this order:

        1. Is `COST_Y1_ADJ` still dominant? It should be important, because healthcare spend is persistent.
        2. Which non-cost variables still rank highly after cost is included? Those are the candidates worth discussing as additional predictors.
        3. Do those non-cost predictors make clinical sense? For this project the most credible groups are:
           - utilization intensity and mix,
           - medication burden and prescription complexity,
           - chronic condition burden,
           - health-status self-report.

        In report language, the key point is not that cost remains predictive. The key point is that **utilization, medication, and disease-burden variables still move the prediction after baseline cost is already known**.
        """
    )

    nb["cells"][22]["source"] = md(
        """
        ### SHAP Interpretation

        SHAP is included only to support a concrete healthcare interpretation. If the plot is dominated entirely by `COST_Y1_ADJ`, then it is not telling a new story.

        Use SHAP to answer:

        - Which features push patients toward worse transition classes within the same Year 1 cost level?
        - Are those pushes clinically plausible, such as higher inpatient use, heavier medication burden, or worse self-rated health?
        - Do the non-cost drivers agree with the simpler feature-importance ranking above?

        If SHAP does not add a clearer story than the simpler importance ranking, it should stay as supporting material, not as a headline figure.
        """
    )

    nb["cells"][21]["source"] = code(
        """
        # SHAP Analysis
        #
        # SHAP is intentionally skipped in the default notebook run because Stage 1 already
        # has several report-grade visuals and the tree explainer adds substantial runtime.
        # If a deeper interpretability appendix is needed, rerun this section manually.
        print("SHAP skipped in default run to keep Stage 1 reproducible and fast.")
        SHAP_AVAILABLE = False
        """
    )

    nb["cells"][25]["source"] = code(
        """
        # Latent score validation: readable plots for routing and healthcare interpretation
        from scipy.stats import spearmanr

        fig, axes = plt.subplots(1, 3, figsize=(22, 6))
        fig.suptitle('Stage 1 Latent Risk Score: What the Score Means', fontsize=15, fontweight='bold', y=1.03)

        direction_palette = {'Improve': '#2ecc71', 'Stable': '#95a5a6', 'Escalate': '#e67e22'}
        trans_colors = {
            0: '#27ae60', 1: '#a8d8a8', 2: '#f1c40f', 3: '#e74c3c',
            4: '#2980b9', 5: '#85c1e9', 6: '#8e44ad',
            7: '#e67e22', 8: '#f5cba7', 9: '#c0392b',
        }

        plot_df = df[['RISK_TIER', 'LATENT_RISK_SCORE', 'DELTA_BIN', 'COST_Y1_ADJ', 'COST_Y2_ADJ']].copy()
        plot_df['Direction3'] = plot_df['RISK_TIER'].map(DIRECTION3_MAP)

        # Panel 1: score by direction (readable summary of whether score tracks worsening)
        ax1 = axes[0]
        dir_order = ['Improve', 'Stable', 'Escalate']
        dir_data = [plot_df.loc[plot_df['Direction3'] == d, 'LATENT_RISK_SCORE'] for d in dir_order]
        bp1 = ax1.boxplot(dir_data, labels=dir_order, patch_artist=True, showfliers=False)
        for patch, d in zip(bp1['boxes'], dir_order):
            patch.set_facecolor(direction_palette[d])
            patch.set_alpha(0.75)
        ax1.set_title('Score Distribution by Transition Direction', fontweight='bold')
        ax1.set_xlabel('Actual Year 2 direction')
        ax1.set_ylabel('LATENT_RISK_SCORE')
        medians = plot_df.groupby('Direction3')['LATENT_RISK_SCORE'].median().reindex(dir_order)
        for x, val in enumerate(medians, start=1):
            ax1.text(x, val + 0.06, f'median={val:.2f}', ha='center', fontsize=9)

        # Panel 2: decile monotonicity with both delta-bin movement and dollar change
        ax2 = axes[1]
        plot_df['_score_decile'] = pd.qcut(
            plot_df['LATENT_RISK_SCORE'].rank(method='first'),
            10,
            labels=[f'D{i}' for i in range(1, 11)]
        )
        decile_stats = plot_df.groupby('_score_decile').agg(
            mean_delta=('DELTA_BIN', 'mean'),
            mean_cost_y1=('COST_Y1_ADJ', 'mean'),
            mean_cost_y2=('COST_Y2_ADJ', 'mean'),
            n=('DELTA_BIN', 'size')
        ).reset_index()
        decile_stats['mean_dollar_change'] = decile_stats['mean_cost_y2'] - decile_stats['mean_cost_y1']

        ax2.bar(decile_stats['_score_decile'], decile_stats['mean_delta'], color='#e67e22', alpha=0.85)
        ax2.axhline(0, color='gray', ls='--', alpha=0.6)
        for x, v in enumerate(decile_stats['mean_delta']):
            ax2.text(x, v + (0.04 if v >= 0 else -0.10), f'{v:.2f}', ha='center', fontsize=8)
        ax2.set_xlabel('Latent risk score decile (D1 = lowest, D10 = highest)')
        ax2.set_ylabel('Mean actual DELTA_BIN')
        ax2.set_title('Higher score deciles should show larger upward movement', fontweight='bold')

        ax2b = ax2.twinx()
        ax2b.plot(decile_stats['_score_decile'], decile_stats['mean_dollar_change'], color='#34495e', marker='o', lw=2)
        ax2b.axhline(0, color='#34495e', ls=':', alpha=0.5)
        ax2b.set_ylabel('Mean dollar change (Y2 - Y1)', color='#34495e')
        ax2b.tick_params(axis='y', colors='#34495e')

        # Panel 3: score separation by 10-class tier
        ax3 = axes[2]
        ordered_tiers = sorted(plot_df['RISK_TIER'].unique())
        score_data = [plot_df.loc[plot_df['RISK_TIER'] == t, 'LATENT_RISK_SCORE'] for t in ordered_tiers]
        bp3 = ax3.boxplot(
            score_data,
            labels=[CLASS_NAMES[t] for t in ordered_tiers],
            patch_artist=True,
            showfliers=False,
        )
        for patch, t in zip(bp3['boxes'], ordered_tiers):
            patch.set_facecolor(trans_colors.get(t, 'gray'))
            patch.set_alpha(0.75)
        ax3.set_xlabel('10-class Stage 1 tier')
        ax3.set_ylabel('LATENT_RISK_SCORE')
        ax3.set_title('Within-level separation: jumpers and escalators should score higher', fontweight='bold')
        ax3.tick_params(axis='x', rotation=35, labelsize=8)

        plt.tight_layout()
        plt.savefig(REPORT_DIR / 'figures' / 'latent_risk_score_analysis.png', dpi=150, bbox_inches='tight')
        plt.show()

        # Focus-class lift chart: easier to interpret than reliability curves
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle('Stage 1 Focus-Class Lift by Predicted-Risk Decile', fontsize=14, fontweight='bold', y=1.03)
        lift_summary_rows = []

        for ax, cls in zip(axes, [3, 9]):
            label = CLASS_NAMES[cls]
            prob_col = f'PROB_{label.upper()}'
            tmp = df[[prob_col, 'RISK_TIER']].copy()
            tmp['is_event'] = (tmp['RISK_TIER'] == cls).astype(int)
            tmp['prob_decile'] = pd.qcut(
                tmp[prob_col].rank(method='first'),
                10,
                labels=[f'D{i}' for i in range(1, 11)]
            )
            dec = tmp.groupby('prob_decile').agg(
                observed_rate=('is_event', 'mean'),
                mean_pred=('is_event', 'size')
            ).reset_index()
            prevalence = tmp['is_event'].mean()
            top_decile_rate = dec.loc[dec['prob_decile'] == 'D10', 'observed_rate'].iloc[0]
            lift = top_decile_rate / max(prevalence, 1e-12)
            lift_summary_rows.append({
                'Class': label,
                'BaseRate': prevalence,
                'TopDecileRate': top_decile_rate,
                'TopDecileLift': lift,
            })

            ax.plot(dec['prob_decile'], dec['observed_rate'], marker='o', lw=2, color='#2c7fb8')
            ax.axhline(prevalence, color='#7f8c8d', ls='--', lw=1.2, label=f'Overall prevalence = {prevalence:.3f}')
            ax.set_title(f'{label}: actual event rate by predicted-risk decile', fontweight='bold')
            ax.set_xlabel('Predicted-risk decile (D10 = highest predicted risk)')
            ax.set_ylabel('Observed event rate')
            ax.legend(fontsize=8)

        plt.tight_layout()
        plt.savefig(REPORT_DIR / 'figures' / 'stage1_reliability_focus_classes.png', dpi=150, bbox_inches='tight')
        plt.show()

        rho_delta = spearmanr(decile_stats.index + 1, decile_stats['mean_delta']).statistic
        rho_change = spearmanr(decile_stats.index + 1, decile_stats['mean_dollar_change']).statistic
        lift_summary_df = pd.DataFrame(lift_summary_rows)

        print("\\n=== Stage 1 Latent Validation Summary ===")
        display(decile_stats)
        print(f"Spearman(decile, mean DELTA_BIN): {rho_delta:.3f}")
        print(f"Spearman(decile, mean dollar change): {rho_change:.3f}")
        print("\\nFocus-class lift summary:")
        display(lift_summary_df)

        for cls in [3, 9]:
            y_true = (df['RISK_TIER'] == cls)
            rec_hard = ((df['pred_class_hard'] == cls) & y_true).sum() / max(y_true.sum(), 1)
            rec_eval = ((df['STAGE1_PRED_CLASS_TUNED'] == cls) & y_true).sum() / max(y_true.sum(), 1)
            print(f"Recall {CLASS_NAMES[cls]:16s}: hard={rec_hard:.3f}, policy_eval={rec_eval:.3f}")

        print(f"Review rate: {df['review_flag'].mean():.3f}")
        print(f"Uncertainty score (mean): {df['uncertainty_score'].mean():.3f}")

        """
    )

    nb["cells"][26]["source"] = md(
        """
        ### Latent Score Interpretation

        These plots should answer three very specific questions.

        **1. Does the latent score represent worsening risk, not just high cost?**

        - In the first panel, patients who truly escalate should sit higher on `LATENT_RISK_SCORE` than stable or improving patients.
        - In the second panel, the mean observed `DELTA_BIN` should rise as score decile increases. That is the direct test that the score is ranking transition severity, not just reproducing Year 1 spending.

        **2. Does the score track spending change in dollars?**

        - The dark line in the second panel shows mean **dollar change (`Y2 - Y1`)** by score decile.
        - This is more faithful to the modeling goal than plotting raw Year 2 cost, because the latent score is supposed to rank **worsening**, not merely expensive patients.

        **3. Are the focus-class probabilities usable as screening signals?**

        - The lift charts replace the earlier reliability curves because they are easier to explain.
        - Each point shows the **actual event rate** inside one predicted-risk decile.
        - If the line rises sharply toward `D10`, then the model is concentrating true `Low_Jumper` or `High_Escalate` cases into the highest-risk patients.
        - That does **not** mean the probability is perfectly calibrated; it means the score is useful for ranking patients for manual review or downstream soft routing.

        **Healthcare reading**

        - `LATENT_RISK_SCORE` is not a final clinical decision rule.
        - Its main value is as a leakage-safe Stage 2 routing signal and as an interpretable “expected worsening” axis that uses more than prior cost alone.
        """
    )

    nb["cells"][28]["source"] = md(
        """
        ---
        ## Summary

        **Stage 1 now serves two distinct purposes**

        1. **Default routing model:** the selected hierarchical classifier remains the default Stage 1 model because it preserves the best overall 10-class structure for Stage 2.
        2. **Screening sensitivity analysis:** one calibrated global policy is retained only to show what happens when we push harder for rare escalation recall.

        **What we intentionally removed from the narrative**

        - We no longer present a long list of near-duplicate policy experiments.
        - We do not treat extremely low rare-class recall as an operational recommendation.
        - We do not rely on threshold tuning as evidence of new signal; the stronger evidence is the gap between the cost-only model and the full model, plus the non-cost features that remain important after baseline cost is included.

        **Stage 1 outputs passed to Stage 2**

        - `PROB_*` / `P_*`: leakage-safe out-of-fold class probabilities
        - `LATENT_RISK_SCORE`, `EXPECTED_DELTA_SCORE`
        - `pred_class_hard`
        - `pred_class_policy`, `review_flag` for sensitivity analysis only
        - `uncertainty_score`

        **Main storytelling takeaway**

        Stage 1 confirms that Year 1 cost is powerful, but it is not the whole story. Utilization mix, medication burden, chronic burden, and engineered transition signals contribute additional information that supports Stage 2 expenditure prediction.
        """
    )

    path.write_text(json.dumps(nb, indent=1))


def update_stage2():
    path = ROOT / "notebooks" / "5.2_stage1_5_and_stage2_modeling.ipynb"
    nb = json.loads(path.read_text())
    clear_outputs(nb)

    nb["cells"][9]["source"] = md(
        """
        ### Interpretation: Healthcare Engagement Score

        **What the x-axis means**

        - Higher `ENGAGEMENT_SCORE` = more office-centered, proactive care.
        - Lower `ENGAGEMENT_SCORE` = more ER/IP-centered, crisis-driven care.

        **Why this matters in healthcare**

        Two patients can have the same total utilization count but very different care patterns. A patient with regular office follow-up and medication refills is clinically different from a patient whose contact is dominated by emergency or inpatient use. This engineered score captures that distinction in one variable.

        **What to look for in the figure**

        - If crisis-mode patients cluster at worse outcomes or higher instability, the score is separating care style, not just volume.
        - If proactive patients still have non-trivial cost, that is not a contradiction. In chronic disease management, structured outpatient care can be expensive but still preferable to avoidable crisis escalation.

        **How we use it**

        `ENGAGEMENT_SCORE` is not a label. It is a compact proxy for care pattern that can help Stage 2 distinguish patients with similar baseline spend but different utilization behavior.
        """
    )

    nb["cells"][12]["source"] = code(
        """
        # VISUALIZATION: Stage 1.5C - Escalation Magnitude

        if 'ESCALATION_MAGNITUDE' in df.columns:

            fig, axes = plt.subplots(1, 3, figsize=(20, 5.5))
            fig.suptitle('Stage 1.5C: Escalation Magnitude — Does the Feature Track Worsening?', fontsize=15, fontweight='bold', y=1.03)

            viz = df[['ESCALATION_MAGNITUDE', 'DELTA_BIN', 'COST_Y1_ADJ', 'COST_Y2_ADJ']].copy()
            viz['DOLLAR_CHANGE'] = viz['COST_Y2_ADJ'] - viz['COST_Y1_ADJ']
            viz['_esc_quintile'] = pd.qcut(
                viz['ESCALATION_MAGNITUDE'].rank(method='first'),
                q=5,
                labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5']
            )

            stats = viz.groupby('_esc_quintile').agg(
                mean_delta=('DELTA_BIN', 'mean'),
                mean_dollar_change=('DOLLAR_CHANGE', 'mean'),
                mean_y1_cost=('COST_Y1_ADJ', 'mean'),
                mean_y2_cost=('COST_Y2_ADJ', 'mean'),
                count=('DELTA_BIN', 'count')
            ).reset_index()

            # Panel 1: actual delta by predicted quintile
            ax1 = axes[0]
            colors = plt.cm.Oranges(np.linspace(0.35, 0.9, 5))
            bars = ax1.bar(stats['_esc_quintile'], stats['mean_delta'], color=colors, edgecolor='white')
            ax1.axhline(0, color='gray', linestyle='--', alpha=0.6)
            for bar, val in zip(bars, stats['mean_delta']):
                ax1.text(bar.get_x() + bar.get_width()/2, val + (0.03 if val >= 0 else -0.08), f'{val:.2f}', ha='center', fontsize=9, fontweight='bold')
            ax1.set_xlabel('Predicted escalation quintile (Q1 = strongest improvement, Q5 = strongest escalation)')
            ax1.set_ylabel('Mean actual DELTA_BIN')
            ax1.set_title('Actual cost-bin movement should rise from Q1 to Q5', fontweight='bold')

            # Panel 2: dollar change rather than raw Y2 cost
            ax2 = axes[1]
            bars2 = ax2.bar(stats['_esc_quintile'], stats['mean_dollar_change'], color=colors, edgecolor='white')
            ax2.axhline(0, color='gray', linestyle='--', alpha=0.6)
            for bar, val in zip(bars2, stats['mean_dollar_change']):
                ax2.text(bar.get_x() + bar.get_width()/2, val, f'${val:,.0f}', ha='center', va='bottom' if val >= 0 else 'top', fontsize=9)
            ax2.set_xlabel('Predicted escalation quintile')
            ax2.set_ylabel('Mean dollar change (Y2 - Y1)')
            ax2.set_title('Higher quintiles should show larger upward spend change', fontweight='bold')

            # Panel 3: predicted magnitude by true delta bin
            ax3 = axes[2]
            delta_order = sorted(viz['DELTA_BIN'].dropna().unique())
            box_data = [viz.loc[viz['DELTA_BIN'] == d, 'ESCALATION_MAGNITUDE'].values for d in delta_order]
            bp = ax3.boxplot(box_data, labels=[str(d) for d in delta_order], patch_artist=True, showfliers=False)
            for patch, c in zip(bp['boxes'], plt.cm.Oranges(np.linspace(0.25, 0.85, len(delta_order)))):
                patch.set_facecolor(c)
                patch.set_alpha(0.8)
            ax3.set_xlabel('Actual DELTA_BIN')
            ax3.set_ylabel('Predicted ESCALATION_MAGNITUDE')
            ax3.set_title('Predicted score should shift upward as true worsening increases', fontweight='bold')

            plt.tight_layout()
            plt.savefig(REPORT_DIR / 'figures' / 'stage1_5c_escalation_magnitude.png', dpi=150, bbox_inches='tight')
            plt.show()
        """
    )

    nb["cells"][13]["source"] = md(
        """
        ### Interpretation: Escalation Magnitude Feature

        This figure is validating an engineered predictor, not a final model output.

        **Axes and meaning**

        - In panel 1, the x-axis is the predicted escalation quintile:
          - `Q1` = patients predicted to improve the most
          - `Q5` = patients predicted to worsen the most
        - The y-axis is the **actual mean `DELTA_BIN`**. If the feature works, this should rise steadily from negative to positive.

        - In panel 2, the y-axis is **mean dollar change (`Y2 - Y1`)**, not raw Year 2 cost.
          That is a more useful healthcare quantity here because the feature is supposed to capture **movement**, not simply absolute spend level.

        - In panel 3, each box shows the distribution of predicted `ESCALATION_MAGNITUDE` for one true `DELTA_BIN` group.
          If the boxes shift upward as actual `DELTA_BIN` increases, the feature is ranking worsening correctly.

        **Healthcare insight**

        `ESCALATION_MAGNITUDE` is useful because it separates two very different situations that raw Y1 cost alone cannot:

        - expensive patients who are likely to improve or stabilize,
        - moderate-cost patients who are likely to jump upward next year.

        That is exactly the kind of feature Stage 2 needs when expenditure is highly skewed and transition direction matters as much as baseline cost.
        """
    )

    nb["cells"][20]["source"] = code(
        """
        # STAGE 1.5E: Raw Rx Feature Visualization (readable summary)

        print()
        print("--- Rx Timeline Feature Visualizations ---")

        RX_VIZ_FEATS = ['RX_DENSITY', 'RX_GAP_RATIO', 'RX_TRAILING_GAP', 'RX_REGULARITY']

        if all(f in df.columns for f in RX_VIZ_FEATS) and df['RX_DENSITY'].notna().sum() > 100:

            hv = df[df['RX_TIMELINE_IMPUTED'] == 0].copy() if 'RX_TIMELINE_IMPUTED' in df.columns else df.copy()
            tier_labels = {t: CLASS_NAMES.get(t, str(t)) for t in sorted(hv['RISK_TIER'].unique())}

            corr_feats = []
            heatmap_feats = []
            for feat in RX_VIZ_FEATS:
                if hv[feat].nunique(dropna=True) > 1 and hv[feat].std() > 1e-8:
                    corr_feats.append(feat)
                    class_medians = hv.groupby('RISK_TIER')[feat].median().round(3)
                    if class_medians.nunique() > 1:
                        heatmap_feats.append(feat)

            if len(corr_feats) == 0:
                print("All Rx timeline features are constant after merge; skipping plot.")
            else:
                corr_rows = []
                for feat in corr_feats:
                    corr_rows.append({
                        'Feature': feat,
                        'Corr_with_Y2_Cost': hv[feat].corr(hv['COST_Y2_ADJ']),
                        'Corr_with_DELTA_BIN': hv[feat].corr(hv['DELTA_BIN']) if 'DELTA_BIN' in hv.columns else np.nan,
                    })
                corr_df = pd.DataFrame(corr_rows).set_index('Feature')

                fig, axes = plt.subplots(1, 2, figsize=(18, 6))
                fig.suptitle('Stage 1.5E: Rx Timeline Features — Coverage and Direction of Signal', fontsize=15, fontweight='bold', y=1.03)

                if heatmap_feats:
                    median_table = (
                        hv.groupby('RISK_TIER')[heatmap_feats]
                        .median()
                        .rename(index=tier_labels)
                    )

                    # Standardize medians for readability across different units
                    heatmap_input = median_table.copy()
                    for col in heatmap_input.columns:
                        col_std = heatmap_input[col].std()
                        if col_std > 1e-12:
                            heatmap_input[col] = (heatmap_input[col] - heatmap_input[col].mean()) / col_std
                        else:
                            heatmap_input[col] = 0.0

                    sns.heatmap(
                        heatmap_input.T,
                        cmap='coolwarm',
                        center=0,
                        annot=median_table.T.round(2),
                        fmt='',
                        linewidths=0.5,
                        ax=axes[0],
                        cbar_kws={'label': 'Standardized class median'}
                    )
                    axes[0].set_title('Class-level Rx pattern (numbers = raw class medians)', fontweight='bold')
                    axes[0].set_xlabel('10-class Stage 1 tier')
                    axes[0].set_ylabel('Rx timeline feature')
                else:
                    axes[0].axis('off')
                    axes[0].text(
                        0.5, 0.5,
                        'Class medians were flat after merge;\\nshowing only the correlation summary on the right.',
                        ha='center', va='center', fontsize=11
                    )

                corr_plot = corr_df[['Corr_with_Y2_Cost', 'Corr_with_DELTA_BIN']]
                corr_plot.plot(kind='barh', ax=axes[1], color=['#e67e22', '#3498db'], edgecolor='white')
                axes[1].axvline(0, color='black', lw=0.8)
                axes[1].set_title('Correlation with cost level vs cost movement', fontweight='bold')
                axes[1].set_xlabel('Pearson correlation')
                axes[1].set_ylabel('')
                axes[1].legend(loc='lower right')

                plt.tight_layout()
                plt.savefig(REPORT_DIR / 'figures' / 'stage1_5e_rx_features.png', dpi=150, bbox_inches='tight')
                plt.show()

                dropped = [f for f in RX_VIZ_FEATS if f not in corr_feats]
                if dropped:
                    print(f"Dropped from plot because they were constant or visually uninformative: {dropped}")

        else:
            print("Rx timeline features not available for visualization.")
        """
    )

    nb["cells"][21]["source"] = md(
        """
        ### Interpretation: Raw Rx Timeline Features (Stage 1.5E)

        The earlier boxplots were difficult to read because these variables are on very different scales and some had almost no variation. This revised figure is answering two simpler questions.

        **Panel 1: Which risk tiers have different refill patterns?**

        - Each cell is one Stage 1 risk tier by one Rx timeline feature.
        - The color shows the median relative to other tiers.
        - The number inside each cell is the **raw median**, so the plot stays interpretable in the original units.
        - If a feature has almost no between-class median variation, we leave it out of the heatmap instead of showing a meaningless row of zeros.

        **Panel 2: Are these features related to cost level or cost movement?**

        - `Corr_with_Y2_Cost` asks whether the feature is associated with higher or lower Year 2 spending.
        - `Corr_with_DELTA_BIN` asks whether it is associated with upward or downward movement in cost bins.

        **Healthcare interpretation**

        - `RX_DENSITY` and `RX_REGULARITY` are closer to medication continuity.
        - `RX_GAP_RATIO` and `RX_TRAILING_GAP` are closer to refill disruption or discontinuation.
        - A feature is most useful when it adds information not already contained in baseline cost and when its sign makes clinical sense.

        If a feature is constant after merge or too sparse to interpret reliably, we drop it from the visual rather than forcing an empty plot into the notebook.
        """
    )

    nb["cells"][25]["source"] = md(
        """
        ### Latent Factors Correlation Matrix

        This heatmap is a **screening tool**, not a proof by itself.

        Use it to answer:

        - Which engineered variables are actually related to Year 2 cost?
        - Which ones are mostly duplicating `LATENT_RISK_SCORE`?
        - Which ones seem to capture a different aspect of risk, such as care pattern, transition direction, or medication continuity?

        A good Stage 1.5 feature does not have to dominate cost prediction on its own. It only needs to add a piece of information that is plausibly useful **after baseline cost is already known**.
        """
    )

    cell29 = "".join(nb["cells"][29]["source"])
    cell29 = cell29.replace(
        """print(
    f"  R2_log={r2_global_log:.4f}, R2_$={r2_global_dollar:.4f}, "
    f"MAE=${mae_global:,.0f}, WMAPE={global_metrics['WMAPE']:.3f}, smear={global_smearing:.3f}"
)

# --- B: Train class-specific experts on TRUE training tiers""",
        """print(
    f"  R2_log={r2_global_log:.4f}, R2_$={r2_global_dollar:.4f}, "
    f"MAE=${mae_global:,.0f}, WMAPE={global_metrics['WMAPE']:.3f}, smear={global_smearing:.3f}"
)
if global_smearing > 5 or global_metrics['WMAPE'] > 2:
    print("  Diagnostic only: standalone global fallback is unstable after log-to-dollar retransformation and is excluded from the report comparison.")

# --- B: Train class-specific experts on TRUE training tiers"""
    )
    cell29 = cell29.replace(
        """# Summary table
strategy_rows = [
    {'Strategy': 'GlobalFallback', **{k: v for k, v in global_metrics.items() if k != 'pred_log'}},
    {'Strategy': 'HardRouting', **{k: v for k, v in hard_metrics.items() if k != 'pred_log'}},
    {'Strategy': 'SoftRouting', **{k: v for k, v in soft_metrics.items() if k != 'pred_log'}},
    {'Strategy': 'SoftRoutingWithFallback', **{k: v for k, v in soft_fb_metrics.items() if k != 'pred_log'}},
]
strategy_summary_df = pd.DataFrame(strategy_rows).sort_values(['MAE', 'R2_log'], ascending=[True, False])""",
        """# Summary table
reportable_strategy_names = ['HardRouting', 'SoftRouting', 'SoftRoutingWithFallback']
strategy_rows = [
    {'Strategy': 'HardRouting', **{k: v for k, v in hard_metrics.items() if k != 'pred_log'}},
    {'Strategy': 'SoftRouting', **{k: v for k, v in soft_metrics.items() if k != 'pred_log'}},
    {'Strategy': 'SoftRoutingWithFallback', **{k: v for k, v in soft_fb_metrics.items() if k != 'pred_log'}},
]
strategy_summary_df = pd.DataFrame(strategy_rows).sort_values(['MAE', 'R2_log'], ascending=[True, False])"""
    )
    nb["cells"][29]["source"] = code(cell29)

    nb["cells"][30]["source"] = code(
        """
        # Evaluation and soft-vs-hard comparison table
        print('\\n--- Detailed Evaluation (Selected Strategy) ---')

        selected_metrics = reg_metrics(y_test, y_pred_test)
        mae = selected_metrics['MAE']
        rmse = selected_metrics['RMSE']
        r2_log = selected_metrics['R2_log']
        r2_dollar = selected_metrics['R2_dollar']
        median_ae = selected_metrics['Median_AE']
        wmape = selected_metrics['WMAPE']

        print(f'  Selected strategy: {best_strategy_name}')
        print(f'  R2 (log scale): {r2_log:.4f}')
        print(f'  R2 (dollar):    {r2_dollar:.4f}')
        print(f'  MAE:            ${mae:,.0f}')
        print(f'  Median AE:      ${median_ae:,.0f}')
        print(f'  RMSE:           ${rmse:,.0f}')
        print(f'  WMAPE:          {wmape:.4f}')

        print('\\n--- Feature Importance by Tier ---')
        for tn, info in tier_models.items():
            imp = info['importance'].sort_values(ascending=False).head(5)
            stage15_in_top = [f for f in imp.index if f in STAGE1_5_FEATS]
            print(f'  {tn}: {", ".join(imp.index.tolist())}')
            if stage15_in_top:
                print(f'    Stage 1.5 in top 5: {", ".join(stage15_in_top)}')

        # Soft vs hard comparison (overall + stratified)
        comparison_rows = []

        for _, row in strategy_summary_df.iterrows():
            comparison_rows.append({
                'Strategy': row['Strategy'],
                'Segment': 'Overall',
                'N': int(len(df_test)),
                'MAE': row['MAE'],
                'R2_log': row['R2_log'],
                'R2_dollar': row['R2_dollar'],
                'WMAPE': row['WMAPE'],
            })

        # Stratify by Stage1 hard class
        for strategy_name in reportable_strategy_names:
            pred = strategy_preds[strategy_name]['dollar']
            for cls in class_order:
                m = stage1_pred_hard_test == cls
                n = int(m.sum())
                if n < 50:
                    continue
                mtr = reg_metrics(y_test[m], pred[m])
                comparison_rows.append({
                    'Strategy': strategy_name,
                    'Segment': f"Stage1Hard_{CLASS_NAMES[int(cls)]}",
                    'N': n,
                    'MAE': mtr['MAE'],
                    'R2_log': mtr['R2_log'],
                    'R2_dollar': mtr['R2_dollar'],
                    'WMAPE': mtr['WMAPE'],
                })

        # Stratify by REVIEW flag
        for strategy_name in reportable_strategy_names:
            pred = strategy_preds[strategy_name]['dollar']
            for flag_val in [0, 1]:
                m = review_flag_test == flag_val
                n = int(m.sum())
                if n < 50:
                    continue
                mtr = reg_metrics(y_test[m], pred[m])
                comparison_rows.append({
                    'Strategy': strategy_name,
                    'Segment': f'ReviewFlag_{flag_val}',
                    'N': n,
                    'MAE': mtr['MAE'],
                    'R2_log': mtr['R2_log'],
                    'R2_dollar': mtr['R2_dollar'],
                    'WMAPE': mtr['WMAPE'],
                })

        stage2_soft_vs_hard_df = pd.DataFrame(comparison_rows)
        comparison_path = REPORT_DIR / 'tables' / 'stage2_soft_vs_hard_comparison.csv'
        stage2_soft_vs_hard_df.to_csv(comparison_path, index=False)

        print(f"\\nSoft-vs-hard comparison saved to: {comparison_path}")
        print("Top overall strategies:")
        display(stage2_soft_vs_hard_df[stage2_soft_vs_hard_df['Segment'] == 'Overall'].sort_values('MAE'))
        """
    )

    nb["cells"][31]["source"] = code(
        """
        # Performance by actual 10-class tier for each routing strategy
        print()
        print('--- Performance by Actual 10-Class Tier ---')

        tier_perf_rows = []
        for strategy_name in reportable_strategy_names:
            pred_bundle = strategy_preds[strategy_name]
            pred_d = pred_bundle['dollar']
            pred_l = pred_bundle['log']

            for tier_val, tier_name in tier_names.items():
                mask = (df_test['RISK_TIER'].to_numpy() == tier_val)
                n = int(mask.sum())
                if n < 25:
                    continue

                y_act = y_test[mask]
                y_act_log = y_test_log[mask]
                tier_perf_rows.append({
                    'Tier': tier_name,
                    'Strategy': strategy_name,
                    'N': n,
                    'Mean_Actual_Cost': float(y_act.mean()),
                    'R2_log': float(r2_score(y_act_log, pred_l[mask])),
                    'R2_dollar': float(r2_score(y_act, pred_d[mask])),
                    'MAE': float(mean_absolute_error(y_act, pred_d[mask])),
                })

        tier_perf_df = pd.DataFrame(tier_perf_rows)

        if tier_perf_df.empty:
            print('No tier had enough test observations for stable within-tier reporting.')
        else:
            tier_perf_path = REPORT_DIR / 'tables' / 'stage2_actual_tier_performance.csv'
            tier_perf_df.to_csv(tier_perf_path, index=False)
            print(f'Saved actual-tier comparison to: {tier_perf_path}')

            for tier_name in tier_names.values():
                sub = tier_perf_df[tier_perf_df['Tier'] == tier_name].sort_values('MAE')
                if sub.empty:
                    continue
                print()
                print(f'{tier_name} (n={int(sub.iloc[0]["N"]):,}, mean=${sub.iloc[0]["Mean_Actual_Cost"]:,.0f})')
                for _, row in sub.iterrows():
                    print(
                        f'  {row["Strategy"]:24s} '
                        f'MAE=${row["MAE"]:>7,.0f}, '
                        f'R2_log={row["R2_log"]:.3f}, '
                        f'R2_$={row["R2_dollar"]:.3f}'
                    )

            mae_pivot = tier_perf_df.pivot(index='Tier', columns='Strategy', values='MAE')
            ordered_tiers = [tier_names[t] for t in sorted(tier_names)]
            mae_pivot = mae_pivot.reindex([t for t in ordered_tiers if t in mae_pivot.index])
            print()
            print('MAE by actual tier (lower is better):')
            display(mae_pivot.round(0))
        """
    )

    nb["cells"][33]["source"] = md(
        """
        ### Stage 2 Results

        **What this section is trying to prove**

        Because expenditure is highly skewed, the question is not just “which regressor is best.” The real question is whether **routing by Stage 1 transition structure** helps us predict Year 2 cost more reliably than one global model.

        **How to read the strategies**

        - `HardRouting`: choose exactly one class-specific expert using the Stage 1 hard/policy class.
        - `SoftRouting`: blend experts using the full Stage 1 probability vector. This is usually safer when Stage 1 has classification noise.
        - `SoftRoutingWithFallback`: same as soft routing, but uncertain cases revert to the global model.

        **Interpretation logic**

        - If `SoftRouting` beats `HardRouting`, that means Stage 1 probabilities contain useful information even when the single hard class is imperfect.
        - If `SoftRoutingWithFallback` helps further, uncertainty is adding value.
        - If it does not help, the fallback rule is probably too blunt and is throwing away useful expert information.
        - The standalone global fallback is kept only as an internal anchor. We do not headline it as a benchmark if the log-to-dollar retransformation is unstable and produces implausible errors.

        In this project, the most important endpoint is **MAE in dollars**, supported by `R2_log` because log-scale fit is more stable under heavy right skew.
        """
    )

    nb["cells"][37]["source"] = md(
        """
        ---
        ## Summary

        **What Stage 2 establishes**

        - Year 2 expenditure is too skewed to model well with a single undifferentiated story.
        - Stage 1 provides routing structure.
        - Stage 1.5 provides engineered predictors that capture care pattern, expected transition magnitude, and prescription continuity.
        - The final comparison tells us whether probability-based routing is more robust than hard class assignment.

        **What to report from this notebook**

        1. Which routing strategy had the best held-out MAE.
        2. Whether the gain came from class-specific experts, soft routing, or both.
        3. Which engineered predictors repeatedly appeared near the top of expert models beyond `COST_Y1_ADJ`.

        **What not to overclaim**

        - A single engineered feature is not a clinical rule by itself.
        - Some Stage 1.5 gains are incremental, not dramatic, and that is expected once strong baseline cost information is already present.
        - The value of the pipeline is the combination of routing plus additional non-cost signal, not any one chart in isolation.
        """
    )

    path.write_text(json.dumps(nb, indent=1))


def main():
    update_stage1()
    update_stage2()


if __name__ == "__main__":
    main()
