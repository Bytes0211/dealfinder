# Apache Zeppelin

**Apache Zeppelin** is a web-based notebook for interactive data analytics, similar to Jupyter Notebook but designed specifically for big data frameworks.

## Key Features

**Multi-Language Support**:
- Spark (Scala, Python, R, SQL)
- Python
- Shell scripts
- Markdown

**Built for Big Data**:
- Native integration with Apache Spark
- Visualizations for DataFrames
- Real-time collaboration (multiple users can edit same notebook)
- Paragraph-level execution (run individual cells)

## Zeppelin vs Jupyter

| Feature | Apache Zeppelin | Jupyter Notebook |
|---------|----------------|------------------|
| **Primary Use** | Big data / Spark-focused | General data science |
| **Built-in Viz** | Yes (charts, graphs) | Requires libraries |
| **Spark Integration** | Native, deeply integrated | Via PySpark library |
| **Collaboration** | Real-time multi-user | Single user (JupyterLab has extensions) |
| **Language Mixing** | Multiple languages in one notebook | One kernel per notebook |
| **Adoption** | Less common | Industry standard |

## In the Deal Finder Context

On AWS EMR, Zeppelin comes pre-installed and is useful for:

1. **Interactive Spark Development**: Test Spark queries against production data
2. **Model Experimentation**: Try different feature engineering approaches
3. **Data Exploration**: Visualize deal price distributions
4. **Team Collaboration**: Multiple data scientists working on same analysis

## Example Use Case

```python
# Paragraph 1: Load data
df = spark.read.parquet("s3://dealfinder/deals/")

# Paragraph 2: Feature engineering
from pyspark.ml.feature import VectorAssembler
assembler = VectorAssembler(inputCols=["price", "discount"], outputCol="features")

# Paragraph 3: Train model
from pyspark.ml.regression import RandomForestRegressor
rf = RandomForestRegressor(featuresCol="features", labelCol="actual_price")
model = rf.fit(training_data)

# Paragraph 4: Visualize results
%sql
SELECT category, AVG(discount) as avg_discount 
FROM deals_table 
GROUP BY category
```

Zeppelin automatically renders the SQL results as an interactive chart.

## Why EMR Includes It

AWS EMR bundles Zeppelin because:
- No setup required (accessible via web UI)
- Secure (integrated with EMR security groups)
- Persistent (notebooks saved to S3)
- Good for data engineers who prefer Spark SQL over Python

## Accessing Zeppelin on EMR

When you launch an EMR cluster, Zeppelin is available at:
```
http://<master-node-public-dns>:8890
```

You can also configure SSH tunneling for secure access:
```bash
ssh -i your-key.pem -N -L 8890:localhost:8890 hadoop@<master-node-public-dns>
```

Then access via: `http://localhost:8890`

## Common Use Cases in Deal Finder

### 1. Data Quality Checks
```sql
%sql
SELECT 
  COUNT(*) as total_deals,
  COUNT(DISTINCT deal_id) as unique_deals,
  SUM(CASE WHEN price IS NULL THEN 1 ELSE 0 END) as null_prices
FROM deals_raw
```

### 2. Feature Engineering Experiments
```python
%pyspark
# Test different discount calculation methods
df_with_features = df.withColumn(
    "discount_percentage",
    (col("estimated_price") - col("actual_price")) / col("estimated_price") * 100
)

df_with_features.describe("discount_percentage").show()
```

### 3. Model Training Visualization
```scala
%spark
// Train multiple models and compare
val models = Seq("RandomForest", "GBT", "LinearRegression")
val results = models.map(modelName => {
  val model = trainModel(modelName, trainingData)
  (modelName, evaluateModel(model, testData))
})

// Zeppelin will auto-render this as a bar chart
z.show(results.toDF("Model", "RMSE"))
```

### 4. Real-Time Query Testing
```python
%pyspark
# Test queries before deploying to production
high_value_deals = spark.sql("""
    SELECT deal_id, title, discount_amount
    FROM deals_evaluated
    WHERE discount_amount > 50
    AND category IN ('Electronics', 'Computers')
    ORDER BY discount_amount DESC
    LIMIT 20
""")

high_value_deals.show()
```

## Best Practices

1. **Save Notebooks to S3**: Configure Zeppelin to persist notebooks to S3 for durability
2. **Use Paragraphs Wisely**: Break complex logic into separate paragraphs for easier debugging
3. **Resource Management**: Be mindful of Spark resources when running large queries
4. **Version Control**: Export notebooks as JSON and commit to Git
5. **Security**: Use EMR security groups to restrict access to Zeppelin web UI

## Alternatives

If Zeppelin doesn't fit your workflow:
- **Jupyter on EMR**: Install JupyterHub on EMR master node
- **AWS EMR Studio**: Managed Jupyter notebooks with EMR integration
- **Local Development**: Use PySpark locally with `spark-submit` for deployment

## Resources

- Official Documentation: https://zeppelin.apache.org/
- EMR Zeppelin Guide: https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-zeppelin.html
- Interpreters: https://zeppelin.apache.org/docs/latest/usage/interpreter/overview.html

---

**Bottom line**: Zeppelin is to Spark what Jupyter is to general Python - an interactive notebook environment, but optimized for big data workloads.
