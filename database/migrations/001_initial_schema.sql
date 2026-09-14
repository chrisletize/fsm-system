--
-- PostgreSQL database dump
--

\restrict WXAlgQ2zeRJd71gtA9gdVWeTzjAkGF0caO7AAXckQVfnceMvdAQkJlKrttFwpgF

-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: fsm_user
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO fsm_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: companies; Type: TABLE; Schema: public; Owner: fsm_user
--

CREATE TABLE public.companies (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.companies OWNER TO fsm_user;

--
-- Name: TABLE companies; Type: COMMENT; Schema: public; Owner: fsm_user
--

COMMENT ON TABLE public.companies IS 'The 4 service companies using the FSM system';


--
-- Name: companies_id_seq; Type: SEQUENCE; Schema: public; Owner: fsm_user
--

CREATE SEQUENCE public.companies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.companies_id_seq OWNER TO fsm_user;

--
-- Name: companies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fsm_user
--

ALTER SEQUENCE public.companies_id_seq OWNED BY public.companies.id;


--
-- Name: customer_job_dates; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.customer_job_dates (
    id integer NOT NULL,
    customer_id integer NOT NULL,
    job_date date NOT NULL,
    source character varying(50) DEFAULT 'servicefusion_import'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    created_by character varying(100)
);


ALTER TABLE public.customer_job_dates OWNER TO fsm_user;

--
-- Name: TABLE customer_job_dates; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.customer_job_dates IS 'Stores job dates from ServiceFusion imports for customer recency analysis';


--
-- Name: customer_job_dates_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.customer_job_dates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.customer_job_dates_id_seq OWNER TO fsm_user;

--
-- Name: customer_job_dates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.customer_job_dates_id_seq OWNED BY public.customer_job_dates.id;


--
-- Name: customers; Type: TABLE; Schema: public; Owner: fsm_user
--

CREATE TABLE public.customers (
    id integer NOT NULL,
    company_id integer NOT NULL,
    account_number character varying(50),
    customer_name character varying(255) NOT NULL,
    contact_first_name character varying(100),
    contact_last_name character varying(100),
    contact_email character varying(255),
    contact_phone character varying(50),
    parent_account_name character varying(255),
    bill_to_address_1 character varying(255),
    bill_to_address_2 character varying(255),
    bill_to_city character varying(100),
    bill_to_state character varying(50),
    bill_to_zip character varying(20),
    service_location_name character varying(255),
    service_location_address_1 character varying(255),
    service_location_address_2 character varying(255),
    service_location_city character varying(100),
    service_location_state character varying(50),
    service_location_zip character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.customers OWNER TO fsm_user;

--
-- Name: TABLE customers; Type: COMMENT; Schema: public; Owner: fsm_user
--

COMMENT ON TABLE public.customers IS 'Customer information across all companies';


--
-- Name: customers_id_seq; Type: SEQUENCE; Schema: public; Owner: fsm_user
--

CREATE SEQUENCE public.customers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.customers_id_seq OWNER TO fsm_user;

--
-- Name: customers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fsm_user
--

ALTER SEQUENCE public.customers_id_seq OWNED BY public.customers.id;


--
-- Name: invoices; Type: TABLE; Schema: public; Owner: fsm_user
--

CREATE TABLE public.invoices (
    id integer NOT NULL,
    company_id integer NOT NULL,
    customer_id integer NOT NULL,
    invoice_number character varying(50) NOT NULL,
    invoice_date date NOT NULL,
    invoice_status character varying(50) NOT NULL,
    invoice_total numeric(10,2) NOT NULL,
    invoice_total_due numeric(10,2) NOT NULL,
    service_total numeric(10,2),
    product_total numeric(10,2),
    tax_total numeric(10,2),
    tax_rate_name character varying(100),
    discount_total numeric(10,2),
    job_amount numeric(10,2),
    job_number character varying(50),
    job_date date,
    job_category character varying(100),
    job_description text,
    assigned_tech character varying(255),
    completion_notes text,
    po_number character varying(50),
    payment_terms character varying(50),
    payment_type character varying(50),
    payment_date date,
    mail_sent_by character varying(100),
    mail_sent_date date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.invoices OWNER TO fsm_user;

--
-- Name: TABLE invoices; Type: COMMENT; Schema: public; Owner: fsm_user
--

COMMENT ON TABLE public.invoices IS 'Invoice records imported from ServiceFusion';


--
-- Name: COLUMN invoices.invoice_status; Type: COMMENT; Schema: public; Owner: fsm_user
--

COMMENT ON COLUMN public.invoices.invoice_status IS 'UNPAID, PAST DUE, PAID, etc';


--
-- Name: COLUMN invoices.invoice_total_due; Type: COMMENT; Schema: public; Owner: fsm_user
--

COMMENT ON COLUMN public.invoices.invoice_total_due IS 'Amount still owed (important for statements)';


--
-- Name: invoices_id_seq; Type: SEQUENCE; Schema: public; Owner: fsm_user
--

CREATE SEQUENCE public.invoices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.invoices_id_seq OWNER TO fsm_user;

--
-- Name: invoices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fsm_user
--

ALTER SEQUENCE public.invoices_id_seq OWNED BY public.invoices.id;


--
-- Name: tax_transactions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tax_transactions (
    id integer NOT NULL,
    company_id integer NOT NULL,
    county character varying(100) NOT NULL,
    invoice_date date NOT NULL,
    invoice_number character varying(50) NOT NULL,
    customer_name character varying(255) NOT NULL,
    job_number character varying(50),
    total_sales numeric(10,2) NOT NULL,
    taxable_amount numeric(10,2) NOT NULL,
    tax_rate character varying(20) NOT NULL,
    tax_collected numeric(10,2) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.tax_transactions OWNER TO fsm_user;

--
-- Name: tax_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tax_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tax_transactions_id_seq OWNER TO fsm_user;

--
-- Name: tax_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tax_transactions_id_seq OWNED BY public.tax_transactions.id;


--
-- Name: companies id; Type: DEFAULT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.companies ALTER COLUMN id SET DEFAULT nextval('public.companies_id_seq'::regclass);


--
-- Name: customer_job_dates id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customer_job_dates ALTER COLUMN id SET DEFAULT nextval('public.customer_job_dates_id_seq'::regclass);


--
-- Name: customers id; Type: DEFAULT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.customers ALTER COLUMN id SET DEFAULT nextval('public.customers_id_seq'::regclass);


--
-- Name: invoices id; Type: DEFAULT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.invoices ALTER COLUMN id SET DEFAULT nextval('public.invoices_id_seq'::regclass);


--
-- Name: tax_transactions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_transactions ALTER COLUMN id SET DEFAULT nextval('public.tax_transactions_id_seq'::regclass);


--
-- Name: companies companies_name_key; Type: CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_name_key UNIQUE (name);


--
-- Name: companies companies_pkey; Type: CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_pkey PRIMARY KEY (id);


--
-- Name: customer_job_dates customer_job_dates_customer_id_job_date_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customer_job_dates
    ADD CONSTRAINT customer_job_dates_customer_id_job_date_key UNIQUE (customer_id, job_date);


--
-- Name: customer_job_dates customer_job_dates_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customer_job_dates
    ADD CONSTRAINT customer_job_dates_pkey PRIMARY KEY (id);


--
-- Name: customers customers_company_id_account_number_key; Type: CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_company_id_account_number_key UNIQUE (company_id, account_number);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: invoices invoices_company_id_invoice_number_key; Type: CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_company_id_invoice_number_key UNIQUE (company_id, invoice_number);


--
-- Name: invoices invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (id);


--
-- Name: tax_transactions tax_transactions_company_id_invoice_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_transactions
    ADD CONSTRAINT tax_transactions_company_id_invoice_number_key UNIQUE (company_id, invoice_number);


--
-- Name: tax_transactions tax_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_transactions
    ADD CONSTRAINT tax_transactions_pkey PRIMARY KEY (id);


--
-- Name: idx_customers_account; Type: INDEX; Schema: public; Owner: fsm_user
--

CREATE INDEX idx_customers_account ON public.customers USING btree (account_number);


--
-- Name: idx_customers_company; Type: INDEX; Schema: public; Owner: fsm_user
--

CREATE INDEX idx_customers_company ON public.customers USING btree (company_id);


--
-- Name: idx_invoices_company; Type: INDEX; Schema: public; Owner: fsm_user
--

CREATE INDEX idx_invoices_company ON public.invoices USING btree (company_id);


--
-- Name: idx_invoices_customer; Type: INDEX; Schema: public; Owner: fsm_user
--

CREATE INDEX idx_invoices_customer ON public.invoices USING btree (customer_id);


--
-- Name: idx_invoices_date; Type: INDEX; Schema: public; Owner: fsm_user
--

CREATE INDEX idx_invoices_date ON public.invoices USING btree (invoice_date);


--
-- Name: idx_invoices_status; Type: INDEX; Schema: public; Owner: fsm_user
--

CREATE INDEX idx_invoices_status ON public.invoices USING btree (invoice_status);


--
-- Name: idx_job_dates_customer_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_job_dates_customer_date ON public.customer_job_dates USING btree (customer_id, job_date DESC);


--
-- Name: idx_job_dates_customer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_job_dates_customer_id ON public.customer_job_dates USING btree (customer_id);


--
-- Name: idx_job_dates_job_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_job_dates_job_date ON public.customer_job_dates USING btree (job_date);


--
-- Name: idx_tax_company_county; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tax_company_county ON public.tax_transactions USING btree (company_id, county);


--
-- Name: idx_tax_customer; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tax_customer ON public.tax_transactions USING btree (customer_name);


--
-- Name: idx_tax_invoice_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tax_invoice_date ON public.tax_transactions USING btree (invoice_date);


--
-- Name: customers update_customers_updated_at; Type: TRIGGER; Schema: public; Owner: fsm_user
--

CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON public.customers FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: invoices update_invoices_updated_at; Type: TRIGGER; Schema: public; Owner: fsm_user
--

CREATE TRIGGER update_invoices_updated_at BEFORE UPDATE ON public.invoices FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: customer_job_dates customer_job_dates_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customer_job_dates
    ADD CONSTRAINT customer_job_dates_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- Name: customers customers_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id);


--
-- Name: invoices invoices_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id);


--
-- Name: invoices invoices_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: fsm_user
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: tax_transactions tax_transactions_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tax_transactions
    ADD CONSTRAINT tax_transactions_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT ALL ON SCHEMA public TO fsm_user;


--
-- Name: TABLE customer_job_dates; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.customer_job_dates TO fsm_user;


--
-- Name: SEQUENCE customer_job_dates_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.customer_job_dates_id_seq TO fsm_user;


--
-- Name: TABLE tax_transactions; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.tax_transactions TO fsm_user;


--
-- Name: SEQUENCE tax_transactions_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT,USAGE ON SEQUENCE public.tax_transactions_id_seq TO fsm_user;


--
-- PostgreSQL database dump complete
--

\unrestrict WXAlgQ2zeRJd71gtA9gdVWeTzjAkGF0caO7AAXckQVfnceMvdAQkJlKrttFwpgF

